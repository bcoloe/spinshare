"""Tests for the DealerService per-member roll workflow and dealer-mode guards."""

from datetime import datetime, timedelta, timezone

import pytest
from app.models import Album, AlbumDeal, GroupAlbum, Review
from app.schemas.album import GroupAlbumStatus, GroupAlbumStatusUpdate
from app.schemas.group_album import NominationGuessCreate
from fastapi import HTTPException, status


@pytest.fixture
def dealer_group(db_session, sample_group):
    """sample_group with dealer mode enabled (1 roll/day by default)."""
    sample_group.settings.dealer_mode = True
    db_session.commit()
    return sample_group


@pytest.fixture
def nominate_albums(db_session, sample_user):
    """Factory: create N albums nominated to a group by sample_user."""

    def _nominate(group, n: int, *, prefix: str = "deal") -> list[GroupAlbum]:
        gas = []
        for i in range(n):
            album = Album(spotify_album_id=f"spotify_{prefix}_{i}", title=f"Album {prefix} {i}", artist="Artist")
            db_session.add(album)
            db_session.flush()
            ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=sample_user.id)
            db_session.add(ga)
            gas.append(ga)
        db_session.commit()
        for ga in gas:
            db_session.refresh(ga)
        return gas

    return _nominate


def _set_rolls_per_day(db_session, group, n: int):
    group.settings.dealer_rolls_per_day = n
    db_session.commit()


# ==================== ROLL ====================


class TestDealerRoll:
    def test_roll_reveals_a_deal(self, dealer_service, dealer_group, sample_user, nominate_albums):
        nominated = nominate_albums(dealer_group, 3)

        result = dealer_service.roll(dealer_group.id, sample_user)

        assert result.rolls_used_today == 1
        assert result.rolls_per_day == 1
        assert result.deal.dealt_at is not None
        assert result.deal.album_id in {ga.album_id for ga in nominated}
        # One deal consumed from the caller's pool of 3
        assert result.pool_remaining == 2

    def test_roll_requires_dealer_mode(self, dealer_service, sample_group, sample_user, nominate_albums):
        nominate_albums(sample_group, 1)

        with pytest.raises(HTTPException) as exc_info:
            dealer_service.roll(sample_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "dealer_mode_disabled"

    def test_roll_requires_membership(self, dealer_service, dealer_group, user_factory, nominate_albums):
        nominate_albums(dealer_group, 1)
        outsider = user_factory(email="out@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc_info:
            dealer_service.roll(dealer_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_roll_respects_daily_limit(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        nominate_albums(dealer_group, 5)
        _set_rolls_per_day(db_session, dealer_group, 2)

        first = dealer_service.roll(dealer_group.id, sample_user)
        second = dealer_service.roll(dealer_group.id, sample_user)
        assert first.rolls_used_today == 1
        assert second.rolls_used_today == 2
        assert first.deal.album_id != second.deal.album_id

        with pytest.raises(HTTPException) as exc_info:
            dealer_service.roll(dealer_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "no_rolls_remaining"

    def test_first_roll_predraws_daily_allotment(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """The first roll of the day caches the full remaining allotment as queued rows."""
        nominate_albums(dealer_group, 5)
        _set_rolls_per_day(db_session, dealer_group, 3)

        dealer_service.roll(dealer_group.id, sample_user)

        queued = (
            db_session.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == dealer_group.id,
                AlbumDeal.user_id == sample_user.id,
                AlbumDeal.revealed_at.is_(None),
            )
            .all()
        )
        revealed = (
            db_session.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == dealer_group.id,
                AlbumDeal.user_id == sample_user.id,
                AlbumDeal.revealed_at.isnot(None),
            )
            .all()
        )
        assert len(revealed) == 1
        assert len(queued) == 2

        # Subsequent rolls reveal from the queue rather than sampling anew
        second = dealer_service.roll(dealer_group.id, sample_user)
        assert second.deal.album_id in {d.album_id for d in queued}

    def test_roll_pool_empty_raises(self, dealer_service, dealer_group, sample_user):
        with pytest.raises(HTTPException) as exc_info:
            dealer_service.roll(dealer_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "dealer_pool_empty"

    def test_roll_excludes_already_dealt_albums(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """Rolling across days never re-deals an album to the same user."""
        nominated = nominate_albums(dealer_group, 2)
        first = dealer_service.roll(dealer_group.id, sample_user)

        # Simulate the first deal having happened yesterday to free up today's roll
        deal = db_session.query(AlbumDeal).filter(AlbumDeal.user_id == sample_user.id).one()
        deal.dealt_at = deal.dealt_at - timedelta(days=1)
        deal.revealed_at = deal.revealed_at - timedelta(days=1)
        db_session.commit()

        second = dealer_service.roll(dealer_group.id, sample_user)
        assert {first.deal.album_id, second.deal.album_id} == {ga.album_id for ga in nominated}

    def test_roll_excludes_reviewed_albums(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        nominated = nominate_albums(dealer_group, 2)
        reviewed_ga, other_ga = nominated
        db_session.add(Review(album_id=reviewed_ga.album_id, user_id=sample_user.id, rating=7.5))
        db_session.commit()

        result = dealer_service.roll(dealer_group.id, sample_user)
        assert result.deal.album_id == other_ga.album_id
        assert result.pool_remaining == 0

    def test_roll_excludes_selected_albums(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """Albums selected before the dealer toggle stay in shared history, not the pool."""
        nominated = nominate_albums(dealer_group, 2)
        selected_ga, pending_ga = nominated
        selected_ga.selected_date = datetime.now(tz=timezone.utc)
        db_session.commit()

        result = dealer_service.roll(dealer_group.id, sample_user)
        assert result.deal.album_id == pending_ga.album_id

    def test_deals_are_per_user(
        self, db_session, dealer_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        """One member's roll does not consume the album from another member's pool."""
        nominated = nominate_albums(dealer_group, 1)
        other = user_factory(email="other@test.com", username="other_member")
        sample_group_service.add_user(dealer_group.id, other.id)

        first = dealer_service.roll(dealer_group.id, sample_user)
        second = dealer_service.roll(dealer_group.id, other)

        assert first.deal.album_id == nominated[0].album_id
        assert second.deal.album_id == nominated[0].album_id

    def test_queued_album_selected_by_shared_draw_is_discarded(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """A queued album that gets selected group-wide (mode toggled off, shared draw
        runs, mode toggled back on) must not be revealed — the roll draws a fresh album."""
        nominated = nominate_albums(dealer_group, 2)
        queued = AlbumDeal(
            group_id=dealer_group.id,
            user_id=sample_user.id,
            album_id=nominated[0].album_id,
        )
        db_session.add(queued)
        db_session.commit()
        queued_id = queued.id

        # Shared draw selects the queued album while dealer mode was off
        nominated[0].selected_date = datetime.now(tz=timezone.utc)
        db_session.commit()

        result = dealer_service.roll(dealer_group.id, sample_user)

        assert result.deal.album_id == nominated[1].album_id
        assert db_session.query(AlbumDeal).filter(AlbumDeal.id == queued_id).first() is None

    def test_queued_album_reviewed_meanwhile_is_discarded(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """A queued album the user has since reviewed (e.g. via another group) is
        discarded instead of revealed."""
        nominated = nominate_albums(dealer_group, 2)
        queued = AlbumDeal(
            group_id=dealer_group.id,
            user_id=sample_user.id,
            album_id=nominated[0].album_id,
        )
        db_session.add(queued)
        db_session.add(Review(album_id=nominated[0].album_id, user_id=sample_user.id, rating=9.0))
        db_session.commit()
        queued_id = queued.id

        result = dealer_service.roll(dealer_group.id, sample_user)

        assert result.deal.album_id == nominated[1].album_id
        assert db_session.query(AlbumDeal).filter(AlbumDeal.id == queued_id).first() is None

    def test_stale_queue_purged_on_roll(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        """Queued rows left over from previous days return to the pool."""
        nominated = nominate_albums(dealer_group, 2)
        stale = AlbumDeal(
            group_id=dealer_group.id,
            user_id=sample_user.id,
            album_id=nominated[0].album_id,
            dealt_at=datetime.now(tz=timezone.utc) - timedelta(days=2),
        )
        db_session.add(stale)
        db_session.commit()
        stale_id = stale.id

        result = dealer_service.roll(dealer_group.id, sample_user)

        assert db_session.query(AlbumDeal).filter(AlbumDeal.id == stale_id).first() is None
        # The formerly-queued album is back in play: either dealt now or still poolable
        assert result.deal.album_id in {ga.album_id for ga in nominated}
        assert result.pool_remaining == 1


# ==================== READS ====================


class TestDealerReads:
    def test_get_todays_deals(self, dealer_service, dealer_group, sample_user, nominate_albums):
        nominate_albums(dealer_group, 2)
        rolled = dealer_service.roll(dealer_group.id, sample_user)

        today = dealer_service.get_todays_deals(dealer_group.id, sample_user)
        assert [d.album_id for d in today.deals] == [rolled.deal.album_id]
        assert today.rolls_used_today == 1
        assert today.rolls_per_day == 1
        assert today.pool_remaining == 1

    def test_get_todays_deals_dealer_off(self, dealer_service, sample_group, sample_user):
        response = dealer_service.get_todays_deals(sample_group.id, sample_user)
        assert response.deals == []
        assert response.rolls_per_day == 0

    def test_get_todays_deals_excludes_previous_days(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        nominate_albums(dealer_group, 2)
        dealer_service.roll(dealer_group.id, sample_user)
        deal = db_session.query(AlbumDeal).filter(AlbumDeal.user_id == sample_user.id).one()
        deal.dealt_at = deal.dealt_at - timedelta(days=1)
        deal.revealed_at = deal.revealed_at - timedelta(days=1)
        db_session.commit()

        today = dealer_service.get_todays_deals(dealer_group.id, sample_user)
        assert today.deals == []
        assert today.rolls_used_today == 0

    def test_member_history_is_union_of_selected_and_dealt(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        nominated = nominate_albums(dealer_group, 3)
        shared_ga = nominated[0]
        shared_ga.selected_date = datetime.now(tz=timezone.utc) - timedelta(days=3)
        db_session.commit()

        rolled = dealer_service.roll(dealer_group.id, sample_user)

        history = dealer_service.get_member_history(dealer_group.id, sample_user)
        by_album = {h.album_id: h for h in history}
        assert set(by_album) == {shared_ga.album_id, rolled.deal.album_id}
        assert by_album[rolled.deal.album_id].dealt_at is not None
        assert by_album[shared_ga.album_id].dealt_at is None
        assert by_album[shared_ga.album_id].selected_date is not None
        # Newest first: today's deal before the 3-day-old shared selection
        assert history[0].album_id == rolled.deal.album_id

    def test_member_history_excludes_other_users_deals(
        self, dealer_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        other = user_factory(email="other@test.com", username="other_member")
        sample_group_service.add_user(dealer_group.id, other.id)
        dealer_service.roll(dealer_group.id, other)

        assert dealer_service.get_member_history(dealer_group.id, sample_user) == []

    def test_member_history_matches_shared_history_in_normal_groups(
        self, db_session, dealer_service, sample_group, sample_user, nominate_albums
    ):
        nominated = nominate_albums(sample_group, 2)
        nominated[0].selected_date = datetime.now(tz=timezone.utc)
        db_session.commit()

        history = dealer_service.get_member_history(sample_group.id, sample_user)
        assert [h.album_id for h in history] == [nominated[0].album_id]

    def test_member_history_skips_deals_with_no_nomination_rows(
        self, db_session, dealer_service, dealer_group, sample_user, nominate_albums
    ):
        nominated = nominate_albums(dealer_group, 1)
        dealer_service.roll(dealer_group.id, sample_user)

        db_session.query(GroupAlbum).filter(GroupAlbum.id == nominated[0].id).delete()
        db_session.commit()

        assert dealer_service.get_member_history(dealer_group.id, sample_user) == []

    def test_get_pool_count(self, dealer_service, dealer_group, sample_user, nominate_albums):
        nominate_albums(dealer_group, 4)
        assert dealer_service.get_pool_count(dealer_group.id, sample_user.id) == 4

        dealer_service.roll(dealer_group.id, sample_user)
        assert dealer_service.get_pool_count(dealer_group.id, sample_user.id) == 3


# ==================== DEALER-MODE GUARDS IN EXISTING SERVICES ====================


class TestDealerGuards:
    def test_cron_selection_skips_dealer_groups(
        self, group_album_service, dealer_group, nominate_albums, db_session
    ):
        nominate_albums(dealer_group, 2)
        assert group_album_service.select_daily_albums(dealer_group.id, n=1) == []
        assert (
            db_session.query(GroupAlbum)
            .filter(GroupAlbum.group_id == dealer_group.id, GroupAlbum.selected_date.isnot(None))
            .count()
            == 0
        )

    def test_trigger_daily_selection_rejected(
        self, group_album_service, dealer_group, sample_user, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.trigger_daily_selection(dealer_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "dealer_mode_enabled"

    def test_catchup_disabled_in_dealer_mode(
        self, db_session, group_album_service, dealer_group, sample_user, nominate_albums
    ):
        dealer_group.settings.catch_up_enabled = True
        db_session.commit()
        nominated = nominate_albums(dealer_group, 1)
        nominated[0].selected_date = datetime.now(tz=timezone.utc) - timedelta(days=2)
        db_session.commit()

        assert group_album_service.get_catchup_albums(dealer_group.id, sample_user) == []

    def test_guess_allowed_on_dealt_album(
        self, db_session, dealer_service, group_album_service, dealer_group, sample_user,
        user_factory, sample_group_service, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        guesser = user_factory(email="guesser@test.com", username="guesser")
        sample_group_service.add_user(dealer_group.id, guesser.id)
        rolled = dealer_service.roll(dealer_group.id, guesser)

        result = group_album_service.check_guess(
            dealer_group.id,
            rolled.deal.id,
            guesser,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        assert result.correct is True

    def test_guess_rejected_on_undealt_pending_album(
        self, group_album_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        nominated = nominate_albums(dealer_group, 1)
        guesser = user_factory(email="guesser@test.com", username="guesser")
        sample_group_service.add_user(dealer_group.id, guesser.id)

        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                dealer_group.id,
                nominated[0].id,
                guesser,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_pending_count_is_per_user_pool(
        self, dealer_service, group_album_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        nominate_albums(dealer_group, 3)
        other = user_factory(email="other@test.com", username="other_member")
        sample_group_service.add_user(dealer_group.id, other.id)

        dealer_service.roll(dealer_group.id, sample_user)

        assert group_album_service.get_pending_nomination_count(dealer_group.id, sample_user) == 2
        assert group_album_service.get_pending_nomination_count(dealer_group.id, other) == 3

    def test_manual_status_selection_rejected(
        self, album_service, dealer_group, sample_user, nominate_albums
    ):
        nominated = nominate_albums(dealer_group, 1)
        with pytest.raises(HTTPException) as exc_info:
            album_service.update_group_album_status(
                dealer_group.id,
                nominated[0].id,
                GroupAlbumStatusUpdate(status=GroupAlbumStatus.Selected),
                sample_user,
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


# ==================== NOMINATION LIFECYCLE ====================


class TestDealerNominationLifecycle:
    def test_remove_user_anonymizes_dealt_nominations(
        self, db_session, dealer_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        """A departing nominator's dealt nominations are anonymized; undealt ones are deleted."""
        nominator = user_factory(email="nom@test.com", username="nominator")
        sample_group_service.add_user(dealer_group.id, nominator.id)
        albums = []
        for i in range(2):
            album = Album(spotify_album_id=f"spotify_leave_{i}", title=f"Leave {i}", artist="Artist")
            db_session.add(album)
            db_session.flush()
            db_session.add(GroupAlbum(group_id=dealer_group.id, album_id=album.id, added_by=nominator.id))
            albums.append(album)
        db_session.commit()

        # Deal the first album to sample_user; leave the second undealt
        db_session.add(
            AlbumDeal(
                group_id=dealer_group.id,
                user_id=sample_user.id,
                album_id=albums[0].id,
                revealed_at=datetime.now(tz=timezone.utc),
            )
        )
        db_session.commit()

        sample_group_service.remove_user(dealer_group.id, nominator.id, nominator.id)

        dealt_ga = (
            db_session.query(GroupAlbum)
            .filter(GroupAlbum.group_id == dealer_group.id, GroupAlbum.album_id == albums[0].id)
            .first()
        )
        undealt_ga = (
            db_session.query(GroupAlbum)
            .filter(GroupAlbum.group_id == dealer_group.id, GroupAlbum.album_id == albums[1].id)
            .first()
        )
        assert dealt_ga is not None
        assert dealt_ga.added_by is None
        assert undealt_ga is None

    def test_remove_user_keeps_departing_members_deals(
        self, db_session, dealer_service, dealer_group, sample_user, user_factory,
        sample_group_service, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        member = user_factory(email="leaver@test.com", username="leaver")
        sample_group_service.add_user(dealer_group.id, member.id)
        dealer_service.roll(dealer_group.id, member)

        sample_group_service.remove_user(dealer_group.id, member.id, member.id)

        deals = db_session.query(AlbumDeal).filter(AlbumDeal.user_id == member.id).all()
        assert len(deals) == 1

    def test_delete_user_anonymizes_dealt_nominations_and_removes_deals(
        self, db_session, dealer_service, sample_user_service, dealer_group, sample_user,
        user_factory, sample_group_service, nominate_albums
    ):
        nominator = user_factory(email="nom@test.com", username="nominator")
        sample_group_service.add_user(dealer_group.id, nominator.id)
        album = Album(spotify_album_id="spotify_del_0", title="Deleted Nominator", artist="Artist")
        db_session.add(album)
        db_session.flush()
        db_session.add(GroupAlbum(group_id=dealer_group.id, album_id=album.id, added_by=nominator.id))
        db_session.commit()

        # Dealt to sample_user, and the nominator has their own deal elsewhere in the group
        db_session.add(
            AlbumDeal(
                group_id=dealer_group.id,
                user_id=sample_user.id,
                album_id=album.id,
                revealed_at=datetime.now(tz=timezone.utc),
            )
        )
        db_session.add(
            AlbumDeal(
                group_id=dealer_group.id,
                user_id=nominator.id,
                album_id=album.id,
                revealed_at=datetime.now(tz=timezone.utc),
            )
        )
        db_session.commit()

        nominator_id = nominator.id
        sample_user_service.delete_user(nominator_id)

        ga = (
            db_session.query(GroupAlbum)
            .filter(GroupAlbum.group_id == dealer_group.id, GroupAlbum.album_id == album.id)
            .first()
        )
        assert ga is not None
        assert ga.added_by is None
        assert (
            db_session.query(AlbumDeal).filter(AlbumDeal.user_id == nominator_id).count() == 0
        )
        # The other member's deal survives
        assert (
            db_session.query(AlbumDeal).filter(AlbumDeal.user_id == sample_user.id).count() == 1
        )

    def test_delete_user_removes_nominations_dealt_only_to_themselves(
        self, db_session, dealer_service, sample_user_service, dealer_group,
        user_factory, sample_group_service
    ):
        """A nomination dealt only to its own (deleted) nominator is removed, not anonymized."""
        nominator = user_factory(email="solo@test.com", username="solo_nom")
        sample_group_service.add_user(dealer_group.id, nominator.id)
        album = Album(spotify_album_id="spotify_solo_0", title="Solo", artist="Artist")
        db_session.add(album)
        db_session.flush()
        db_session.add(GroupAlbum(group_id=dealer_group.id, album_id=album.id, added_by=nominator.id))
        db_session.add(
            AlbumDeal(
                group_id=dealer_group.id,
                user_id=nominator.id,
                album_id=album.id,
                revealed_at=datetime.now(tz=timezone.utc),
            )
        )
        db_session.commit()

        sample_user_service.delete_user(nominator.id)

        assert (
            db_session.query(GroupAlbum)
            .filter(GroupAlbum.group_id == dealer_group.id, GroupAlbum.album_id == album.id)
            .first()
            is None
        )


# ==================== REVIEW HISTORY UNION ====================


class TestDealerReviewHistory:
    def test_my_group_reviews_include_dealt_albums(
        self, db_session, dealer_service, review_service, dealer_group, sample_user, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        rolled = dealer_service.roll(dealer_group.id, sample_user)
        db_session.add(Review(album_id=rolled.deal.album_id, user_id=sample_user.id, rating=8.0))
        db_session.commit()

        reviews = review_service.get_my_reviews_for_group(dealer_group.id, sample_user.id)
        assert [r.album_id for r in reviews] == [rolled.deal.album_id]

    def test_all_group_reviews_include_albums_dealt_to_anyone(
        self, db_session, dealer_service, review_service, dealer_group, sample_user,
        user_factory, sample_group_service, nominate_albums
    ):
        nominate_albums(dealer_group, 1)
        other = user_factory(email="other@test.com", username="other_member")
        sample_group_service.add_user(dealer_group.id, other.id)
        rolled = dealer_service.roll(dealer_group.id, other)
        db_session.add(Review(album_id=rolled.deal.album_id, user_id=other.id, rating=6.0))
        db_session.commit()

        reviews = review_service.get_all_reviews_for_group(dealer_group.id, sample_user.id)
        assert [r.album_id for r in reviews] == [rolled.deal.album_id]
