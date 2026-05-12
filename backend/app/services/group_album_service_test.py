from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from app.models import Album, GroupAlbum
from app.models.group_settings import GroupSettings
from app.schemas.group_album import NominationGuessCreate
from fastapi import HTTPException, status


def _mark_selected(db_session, group_album: GroupAlbum):
    """Set selected_date to simulate cron having selected this album."""
    group_album.selected_date = datetime.now(tz=timezone.utc)
    db_session.commit()
    db_session.refresh(group_album)


# ==================== DAILY SELECTION ====================


class TestSelectDailyAlbums:
    def test_select_one_album(
        self, group_album_service, sample_group, sample_group_album
    ):
        results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].id == sample_group_album.id
        assert results[0].selected_date is not None

    def test_select_multiple_albums(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        from app.models import Album

        album2 = Album(spotify_album_id="spotify_2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)

        ga2 = GroupAlbum(
            group_id=sample_group.id, album_id=album2.id, added_by=sample_user.id
        )
        db_session.add(ga2)
        db_session.commit()

        results = group_album_service.select_daily_albums(sample_group.id, n=2)
        assert len(results) == 2
        assert all(ga.selected_date is not None for ga in results)

    def test_select_idempotent_same_day(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """Calling select_daily_albums again on the same day returns existing selection."""
        _mark_selected(db_session, sample_group_album)
        results = group_album_service.select_daily_albums(sample_group.id, n=1)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_select_idempotent_does_not_add_more(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        """Running selection twice on the same day does not add new albums even if pool has more."""
        group_album_service.select_daily_albums(sample_group.id, n=1)

        album2 = Album(spotify_album_id="spotify_idem_2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)
        ga2 = GroupAlbum(group_id=sample_group.id, album_id=album2.id, added_by=sample_user.id)
        db_session.add(ga2)
        db_session.commit()

        second = group_album_service.select_daily_albums(sample_group.id, n=1)
        assert len(second) == 1
        assert second[0].id == sample_group_album.id

    def test_select_partial_pool_returns_available(
        self, group_album_service, sample_group, sample_group_album
    ):
        """When pool has fewer albums than requested, select all available instead of failing."""
        results = group_album_service.select_daily_albums(sample_group.id, n=5)
        assert len(results) == 1
        assert results[0].selected_date is not None

    def test_select_partial_pool_sends_notifications(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        """Partial pool selection creates a pool-low notification for each group member."""
        from app.models.notification import Notification
        from app.schemas.notification import NotificationType

        group_album_service.select_daily_albums(sample_group.id, n=5)

        notif = db_session.query(Notification).filter(
            Notification.user_id == sample_user.id,
            Notification.type == NotificationType.nomination_pool_low,
        ).first()
        assert notif is not None
        assert notif.group_id == sample_group.id

    def test_select_empty_group_raises(self, group_album_service, sample_group):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_daily_albums(sample_group.id, n=1)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_multi_nomination_counts_as_one_album(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session
    ):
        """Two nominations for the same album should count as one selectable album."""
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(ga2)
        db_session.commit()

        results = group_album_service.select_daily_albums(sample_group.id, n=1)
        assert len(results) == 1

    def test_multi_nomination_all_marked_selected(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session
    ):
        """Selecting a multiply-nominated album marks ALL nominations as selected."""
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(ga2)
        db_session.commit()
        db_session.refresh(ga2)

        group_album_service.select_daily_albums(sample_group.id, n=1)

        db_session.refresh(sample_group_album)
        db_session.refresh(ga2)
        assert sample_group_album.selected_date is not None
        assert ga2.selected_date is not None


class TestGetPendingNominationCount:
    def test_counts_pending_nominations(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        count = group_album_service.get_pending_nomination_count(sample_group.id, sample_user)
        assert count == 1

    def test_excludes_selected_nominations(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        count = group_album_service.get_pending_nomination_count(sample_group.id, sample_user)
        assert count == 0

    def test_deduplicates_multi_nominated_album(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session
    ):
        """Two nominations for the same album should count as 1 pending album."""
        other = user_factory(email="other2@test.com", username="other2")
        sample_group_service.add_user(sample_group.id, other.id)
        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(ga2)
        db_session.commit()

        count = group_album_service.get_pending_nomination_count(sample_group.id, sample_user)
        assert count == 1

    def test_non_member_forbidden(self, group_album_service, sample_group, user_factory):
        outsider = user_factory(email="out2@test.com", username="outsider2")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_pending_nomination_count(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_global_group_counts_all_non_global_nominations(
        self,
        group_album_service,
        sample_group_service,
        global_group,
        sample_group,
        sample_album,
        sample_user,
        db_session,
    ):
        """Global group pool count reflects unspun nominations across all non-global groups."""
        sample_group_service.add_user(global_group.id, sample_user.id)
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        count = group_album_service.get_pending_nomination_count(global_group.id, sample_user)
        assert count == 1

    def test_global_group_excludes_already_spun(
        self,
        group_album_service,
        sample_group_service,
        global_group,
        sample_group,
        sample_album,
        sample_user,
        db_session,
    ):
        """Albums already spun in the global group are excluded from the pool count."""
        sample_group_service.add_user(global_group.id, sample_user.id)
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        group_album_service.select_daily_albums(global_group.id, n=1)

        count = group_album_service.get_pending_nomination_count(global_group.id, sample_user)
        assert count == 0


class TestTriggerDailySelection:
    def test_selects_when_none_today(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].selected_date is not None

    def test_idempotent_returns_existing(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_non_member_forbidden(
        self, group_album_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.trigger_daily_selection(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_not_enough_albums_raises(
        self, group_album_service, sample_group, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_respects_daily_album_count(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        db_session
    ):
        from app.models import Album, GroupSettings

        album2 = Album(spotify_album_id="spotify_2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)
        ga2 = GroupAlbum(group_id=sample_group.id, album_id=album2.id, added_by=sample_user.id)
        db_session.add(ga2)

        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).first()
        settings.daily_album_count = 2
        db_session.commit()

        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 2


class TestGetTodaysAlbums:
    def test_returns_todays_selections(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        results = group_album_service.get_todays_albums(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_excludes_unselected(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        results = group_album_service.get_todays_albums(sample_group.id, sample_user)
        assert results == []

    def test_non_member_forbidden(
        self, group_album_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_todays_albums(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GUESSING ====================


class TestCheckGuess:
    def test_correct_guess(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        # other guesses sample_user (the actual nominator)
        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        assert result.correct is True
        assert sample_user.id in result.nominator_user_ids
        assert sample_user.username in result.nominator_usernames
        assert result.guess.guessing_user_id == other.id

    def test_incorrect_guess(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)

        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=third.id),  # wrong guess
        )

        assert result.correct is False
        assert sample_user.id in result.nominator_user_ids  # actual nominator revealed anyway

    def test_correct_guess_for_co_nominator(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        """Guessing any co-nominator of a multiply-nominated album should be correct."""
        other = user_factory(email="other@test.com", username="other_user")
        guesser = user_factory(email="guesser@test.com", username="guesser")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, guesser.id)

        # other also nominates the same album
        co_nomination = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(co_nomination)
        db_session.commit()

        # Mark both as selected
        _mark_selected(db_session, sample_group_album)
        co_nomination.selected_date = sample_group_album.selected_date
        db_session.commit()

        # Guessing the co-nominator should be correct
        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            guesser,
            NominationGuessCreate(guessed_user_id=other.id),
        )

        assert result.correct is True
        assert other.id in result.nominator_user_ids
        assert sample_user.id in result.nominator_user_ids

    def test_not_selected_raises(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_self_guess_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _mark_selected(db_session, sample_group_album)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                sample_user,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_guess_conflict(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_non_member_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        user_factory,
        db_session,
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        _mark_selected(db_session, sample_group_album)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                outsider,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestGetMyGuess:
    def test_get_my_guess_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)
        group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        result = group_album_service.get_my_guess(sample_group.id, sample_group_album.id, other)
        assert result.guess.guessing_user_id == other.id
        assert result.correct is True
        assert sample_user.id in result.nominator_user_ids
        assert sample_user.username in result.nominator_usernames

    def test_get_my_guess_not_found(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_my_guess(
                sample_group.id, sample_group_album.id, sample_user
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_non_member_forbidden(
        self, group_album_service, sample_group, sample_group_album, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_my_guess(
                sample_group.id, sample_group_album.id, outsider
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GUESS OPTIONS ====================


class TestGetGuessOptions:
    def test_returns_all_members_when_under_cap(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)

        result = group_album_service.get_guess_options(
            sample_group.id, sample_group_album.id, other
        )
        option_ids = {o.user_id for o in result.options}
        # Both members present (group has 2; default cap is 5)
        assert sample_user.id in option_ids
        assert other.id in option_ids

    def test_nominator_always_included_when_capped(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        """With a cap of 2, the nominator must be in the pool even when there are many members."""
        # Add 4 extra members so total = 5 (> cap of 2)
        extras = [
            user_factory(email=f"extra{i}@test.com", username=f"extra{i}") for i in range(4)
        ]
        for u in extras:
            sample_group_service.add_user(sample_group.id, u.id)

        # Force cap to 2 on the group settings
        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).first()
        settings.guess_user_cap = 2
        db_session.commit()

        result = group_album_service.get_guess_options(
            sample_group.id, sample_group_album.id, extras[0]
        )
        assert len(result.options) == 2
        option_ids = {o.user_id for o in result.options}
        # sample_user is the nominator — must always be included
        assert sample_user.id in option_ids

    def test_pool_is_deterministic(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        """Two different callers receive identical option sets."""
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)

        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).first()
        settings.guess_user_cap = 2
        db_session.commit()

        result_a = group_album_service.get_guess_options(sample_group.id, sample_group_album.id, other)
        result_b = group_album_service.get_guess_options(sample_group.id, sample_group_album.id, third)
        assert {o.user_id for o in result_a.options} == {o.user_id for o in result_b.options}

    def test_non_member_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        user_factory,
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_guess_options(sample_group.id, sample_group_album.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GLOBAL GROUP SELECTION ====================


def _make_album(db_session, spotify_id: str, title: str) -> Album:
    album = Album(spotify_album_id=spotify_id, title=title, artist="Test Artist")
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album


class TestGlobalGroupSelection:
    def test_global_group_samples_from_all_nominations(
        self,
        db_session,
        group_album_service,
        global_group,
        sample_group,
        sample_album,
        sample_user,
    ):
        """Global group selection pulls from nominations in other groups."""
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        results = group_album_service.select_daily_albums(global_group.id, n=1)

        assert len(results) == 1
        assert results[0].album_id == sample_album.id
        assert results[0].group_id == global_group.id
        assert results[0].selected_date is not None

    def test_global_group_excludes_already_spun(
        self,
        db_session,
        group_album_service,
        global_group,
        sample_group,
        sample_album,
        sample_user,
    ):
        """Albums already spun in the global group are not re-selected on a subsequent day."""
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        group_album_service.select_daily_albums(global_group.id, n=1)

        # Backdate the selection to yesterday so the idempotency guard does not fire,
        # letting us verify the cross-day exclusion logic independently.
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        global_ga = db_session.query(GroupAlbum).filter(GroupAlbum.group_id == global_group.id).first()
        global_ga.selected_date = yesterday
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_daily_albums(global_group.id, n=1)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_global_group_pools_across_multiple_groups(
        self,
        db_session,
        group_album_service,
        global_group,
        sample_group,
        sample_album,
        sample_user,
        group_factory,
    ):
        """Nominations from different groups are all eligible."""
        album2 = _make_album(db_session, "spot_2", "Kid A")

        other_group = group_factory(name="other-group")
        ga1 = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        ga2 = GroupAlbum(group_id=other_group.id, album_id=album2.id, added_by=sample_user.id)
        db_session.add_all([ga1, ga2])
        db_session.commit()

        results = group_album_service.select_daily_albums(global_group.id, n=2)
        selected_album_ids = {r.album_id for r in results}
        assert selected_album_ids == {sample_album.id, album2.id}


# ==================== CHAOS MODE ====================


def _enable_chaos(db_session, group):
    settings = db_session.query(GroupSettings).filter_by(group_id=group.id).first()
    settings.chaos_mode = True
    db_session.commit()


def _make_unrelated_album(db_session, spotify_id="chaos_spot_1", title="Chaos Album") -> Album:
    album = Album(spotify_album_id=spotify_id, title=title, artist="Mystery Artist")
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album


class TestChaosSelection:
    def test_chaos_album_marked_as_chaos(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """When chaos fires, the resulting GroupAlbum has is_chaos_selection=True."""
        _enable_chaos(db_session, sample_group)
        chaos_album = _make_unrelated_album(db_session)

        # Force all slots to be chaos
        with patch("app.services.group_album_service.random.random", return_value=0.0):
            results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].is_chaos_selection is True
        assert results[0].album_id == chaos_album.id
        assert results[0].added_by is None

    def test_chaos_album_excluded_from_pool_on_next_run(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """A chaos-selected album is not re-eligible in subsequent selections."""
        _enable_chaos(db_session, sample_group)
        _make_unrelated_album(db_session)

        with patch("app.services.group_album_service.random.random", return_value=0.0):
            group_album_service.select_daily_albums(sample_group.id, n=1)

        # The group now has both the nominated album and the chaos album.
        # No unrelated albums remain in the global pool.
        # Advance to the next day so the idempotency check doesn't return yesterday's pick.
        from datetime import date

        next_day = date(2099, 1, 2)
        with (
            patch("app.services.group_album_service.random.random", return_value=0.0),
            patch("app.services.group_album_service._group_today", return_value=next_day),
        ):
            # Only the nominated album is unselected — chaos has nothing to pull from,
            # so it falls back to normal selection.
            results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].is_chaos_selection is False

    def test_no_chaos_when_probability_not_hit(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """When random.random always returns above the chaos threshold, only normal picks happen."""
        _enable_chaos(db_session, sample_group)
        _make_unrelated_album(db_session)

        with patch("app.services.group_album_service.random.random", return_value=1.0):
            results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].is_chaos_selection is False
        assert results[0].album_id == sample_group_album.album_id

    def test_chaos_mode_off_uses_normal_selection(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """With chaos_mode disabled, random.random=0.0 has no effect — normal selection runs."""
        _make_unrelated_album(db_session)

        with patch("app.services.group_album_service.random.random", return_value=0.0):
            results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].is_chaos_selection is False

    def test_mixed_chaos_and_normal_slots(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        """n=2 with chaos on first slot and normal on second produces one of each."""
        _enable_chaos(db_session, sample_group)
        chaos_album = _make_unrelated_album(db_session)

        album2 = Album(spotify_album_id="spot_2", title="Second Album", artist="Band")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)
        from app.models import GroupAlbum as GA
        ga2 = GA(group_id=sample_group.id, album_id=album2.id, added_by=sample_group_album.added_by)
        db_session.add(ga2)
        db_session.commit()

        # First call: chaos; second call: normal
        call_count = [0]

        def alternating_random():
            call_count[0] += 1
            return 0.0 if call_count[0] == 1 else 1.0

        with patch("app.services.group_album_service.random.random", side_effect=alternating_random):
            results = group_album_service.select_daily_albums(sample_group.id, n=2)

        assert len(results) == 2
        chaos_results = [r for r in results if r.is_chaos_selection]
        normal_results = [r for r in results if not r.is_chaos_selection]
        assert len(chaos_results) == 1
        assert len(normal_results) == 1
        assert chaos_results[0].album_id == chaos_album.id


class TestChaosGuess:
    def _make_chaos_group_album(self, db_session, group, album) -> GroupAlbum:
        """Insert a chaos-selected GroupAlbum (no nominator)."""
        ga = GroupAlbum(
            group_id=group.id,
            album_id=album.id,
            added_by=None,
            selected_date=datetime.now(tz=timezone.utc),
            is_chaos_selection=True,
        )
        db_session.add(ga)
        db_session.commit()
        db_session.refresh(ga)
        return ga

    def test_chaos_guess_correct_for_chaos_album(
        self, group_album_service, sample_group, sample_user, db_session
    ):
        chaos_album = _make_unrelated_album(db_session)
        chaos_ga = self._make_chaos_group_album(db_session, sample_group, chaos_album)

        result = group_album_service.check_guess(
            sample_group.id,
            chaos_ga.id,
            sample_user,
            NominationGuessCreate(guessed_user_id=None),
        )

        assert result.correct is True
        assert result.is_chaos_selection is True
        assert result.nominator_user_ids == []
        assert result.nominator_usernames == []
        assert result.guess.guessed_user_id is None

    def test_chaos_guess_incorrect_for_normal_album(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=None),
        )

        assert result.correct is False
        assert result.is_chaos_selection is False
        assert sample_user.id in result.nominator_user_ids

    def test_user_guess_incorrect_for_chaos_album(
        self, group_album_service, sample_group, sample_user, user_factory, sample_group_service, db_session
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)

        chaos_album = _make_unrelated_album(db_session)
        chaos_ga = self._make_chaos_group_album(db_session, sample_group, chaos_album)

        result = group_album_service.check_guess(
            sample_group.id,
            chaos_ga.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        assert result.correct is False
        assert result.is_chaos_selection is True

    def test_normal_guess_returns_is_chaos_false(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        assert result.is_chaos_selection is False


class TestChaosGuessOptions:
    def test_has_chaos_option_when_chaos_mode_enabled(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _enable_chaos(db_session, sample_group)
        result = group_album_service.get_guess_options(
            sample_group.id, sample_group_album.id, sample_user
        )
        assert result.has_chaos_option is True

    def test_no_chaos_option_when_chaos_mode_disabled(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        result = group_album_service.get_guess_options(
            sample_group.id, sample_group_album.id, sample_user
        )
        assert result.has_chaos_option is False
