"""Tests for ParticipationService (priority-pick credits)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, status

from app.models import (
    GroupAlbum,
    GroupParticipation,
    GroupSettings,
    PriorityReviewCredit,
    Review,
)
from app.services.participation_service import ParticipationService


@pytest.fixture
def participation_service(db_session) -> ParticipationService:
    return ParticipationService(db_session)


def _set_threshold(db_session, group_id: int, threshold: int | None) -> None:
    settings = (
        db_session.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
    )
    settings.priority_pick_threshold = threshold
    db_session.commit()


def _make_review(db_session, user, album, is_draft=False) -> Review:
    review = Review(user_id=user.id, album_id=album.id, rating=8.0, is_draft=is_draft)
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    return review


def _nominate(db_session, group, user, album) -> GroupAlbum:
    """Make ``album`` a member of ``group`` (a pending nomination)."""
    ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=user.id)
    db_session.add(ga)
    db_session.commit()
    db_session.refresh(ga)
    return ga


def _draw(db_session, group, user, album) -> GroupAlbum:
    """Nominate ``album`` and mark it drawn (selected) in ``group``."""
    ga = _nominate(db_session, group, user, album)
    ga.selected_date = datetime.now(tz=timezone.utc)
    db_session.commit()
    db_session.refresh(ga)
    return ga


def _ledger_count(db_session, group_id, user_id) -> int:
    return (
        db_session.query(PriorityReviewCredit)
        .filter(
            PriorityReviewCredit.group_id == group_id,
            PriorityReviewCredit.user_id == user_id,
        )
        .count()
    )


class TestAwardReviewCredit:
    def test_awards_one_credit(self, participation_service, db_session, sample_group, sample_user, sample_album):
        _set_threshold(db_session, sample_group.id, 3)
        _draw(db_session, sample_group, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 1

    def test_noop_when_only_nominated_not_drawn(self, participation_service, db_session, sample_group, sample_user, sample_album):
        """Reviewing an album that is nominated but not yet drawn earns nothing —
        credit is owed only once the album is actually drawn into the group."""
        _set_threshold(db_session, sample_group.id, 3)
        _nominate(db_session, sample_group, sample_user, sample_album)  # pending, never drawn
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service._get(sample_group.id, sample_user.id) is None
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 0

    def test_idempotent_on_repeat(self, participation_service, db_session, sample_group, sample_user, sample_album):
        _set_threshold(db_session, sample_group.id, 3)
        _draw(db_session, sample_group, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)
        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 1

    def test_noop_when_album_not_in_group(self, participation_service, db_session, sample_group, sample_user, sample_album):
        _set_threshold(db_session, sample_group.id, 3)
        # Album is reviewed but never nominated/selected in the group.
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service._get(sample_group.id, sample_user.id) is None
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 0

    def test_noop_when_threshold_unset(self, participation_service, db_session, sample_group, sample_user, sample_album):
        _set_threshold(db_session, sample_group.id, None)
        _draw(db_session, sample_group, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service._get(sample_group.id, sample_user.id) is None

    def test_noop_for_global_group(self, participation_service, db_session, global_group, sample_user, sample_album):
        _set_threshold(db_session, global_group.id, 3)
        _draw(db_session, global_group, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert _ledger_count(db_session, global_group.id, sample_user.id) == 0

    def test_noop_for_dealer_group(self, participation_service, db_session, sample_group, sample_user, sample_album):
        settings = db_session.query(GroupSettings).filter(GroupSettings.group_id == sample_group.id).first()
        settings.priority_pick_threshold = 3
        settings.dealer_mode = True
        db_session.commit()
        _draw(db_session, sample_group, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 0

    def test_noop_for_non_member(self, participation_service, db_session, sample_group, sample_album, user_factory):
        _set_threshold(db_session, sample_group.id, 3)
        outsider = user_factory(email="out@test.com", username="outsider")
        _draw(db_session, sample_group, outsider, sample_album)
        review = _make_review(db_session, outsider, sample_album)

        participation_service.award_review_credit(outsider.id, review)

        assert participation_service._get(sample_group.id, outsider.id) is None

    def test_credits_every_group_the_album_belongs_to(
        self, participation_service, db_session, sample_group, sample_user, sample_album, group_factory
    ):
        """A single review credits each group that has drawn the album — the ledger
        keeps crediting per-group idempotent and independent of any request context."""
        _set_threshold(db_session, sample_group.id, 3)
        _draw(db_session, sample_group, sample_user, sample_album)
        group2 = group_factory(name="Second", user=sample_user)
        _set_threshold(db_session, group2.id, 3)
        _draw(db_session, group2, sample_user, sample_album)
        review = _make_review(db_session, sample_user, sample_album)

        participation_service.award_review_credit(sample_user.id, review)

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1
        assert participation_service.get_progress(group2.id, sample_user.id).credits == 1


class TestAwardReviewCreditFromAlbumPage:
    """Regression: a review published without a group_id (album page) must still
    credit a group the album was already drawn into — the draw-time backfill has
    already passed, so only the publish hook can catch it."""

    def test_album_page_review_credits_already_drawn_album(
        self, review_service, participation_service, db_session, sample_group, sample_user, sample_album
    ):
        from app.schemas.album import ReviewCreate

        _set_threshold(db_session, sample_group.id, 3)
        _draw(db_session, sample_group, sample_user, sample_album)

        # group_id omitted, exactly as the album page submits a review.
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=8.0))

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1

    def test_album_page_publish_via_update_credits(
        self, review_service, participation_service, db_session, sample_group, sample_user, sample_album
    ):
        from app.schemas.album import ReviewCreate, ReviewUpdate

        _set_threshold(db_session, sample_group.id, 3)
        _draw(db_session, sample_group, sample_user, sample_album)

        # Save a draft (no credit), then publish it from the album page (no group_id).
        draft = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=8.0, is_draft=True)
        )
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 0

        review_service.update_review(draft.id, sample_user.id, ReviewUpdate(is_draft=False))

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1


class TestGetProgress:
    def test_disabled_when_threshold_unset(self, participation_service, db_session, sample_group, sample_user):
        _set_threshold(db_session, sample_group.id, None)
        progress = participation_service.get_progress(sample_group.id, sample_user.id)
        assert progress.threshold is None
        assert progress.credits == 0
        assert progress.can_pick is False

    def test_can_pick_when_at_threshold(self, participation_service, db_session, sample_group, sample_user):
        _set_threshold(db_session, sample_group.id, 2)
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=2))
        db_session.commit()

        progress = participation_service.get_progress(sample_group.id, sample_user.id)
        assert progress.credits == 2
        assert progress.can_pick is True
        assert progress.pending_pick is None

    def test_cannot_pick_when_pick_pending(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, 2)
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, credits=5,
            priority_group_album_id=sample_group_album.id,
            priority_queued_at=datetime.now(tz=timezone.utc),
        ))
        db_session.commit()

        progress = participation_service.get_progress(sample_group.id, sample_user.id)
        assert progress.can_pick is False
        assert progress.pending_pick is not None
        assert progress.pending_pick.id == sample_group_album.id


class TestSetPriorityPick:
    def test_success(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, 2)
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=2))
        db_session.commit()

        progress = participation_service.set_priority_pick(
            sample_group.id, sample_user.id, sample_group_album.id
        )
        assert progress.pending_pick.id == sample_group_album.id
        assert progress.can_pick is False
        # Credits are not debited until the album is drawn.
        assert progress.credits == 2

    def test_insufficient_credits(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, 3)
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=2))
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, sample_user.id, sample_group_album.id)
        assert exc.value.status_code == status.HTTP_409_CONFLICT
        assert exc.value.detail == "insufficient_credits"

    def test_already_queued(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, 2)
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, credits=5,
            priority_group_album_id=sample_group_album.id,
            priority_queued_at=datetime.now(tz=timezone.utc),
        ))
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, sample_user.id, sample_group_album.id)
        assert exc.value.detail == "pick_already_queued"

    def test_disabled(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, None)
        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, sample_user.id, sample_group_album.id)
        assert exc.value.detail == "priority_pick_disabled"

    def test_non_member_forbidden(self, participation_service, db_session, sample_group, sample_group_album, user_factory):
        _set_threshold(db_session, sample_group.id, 1)
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, outsider.id, sample_group_album.id)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_album_not_owned_by_caller(self, participation_service, db_session, sample_group, sample_user, sample_album, user_factory):
        _set_threshold(db_session, sample_group.id, 1)
        other = user_factory(email="o@test.com", username="other")
        # A nomination added by someone else
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=other.id)
        db_session.add(ga)
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=3))
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, sample_user.id, ga.id)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    def test_album_already_selected(self, participation_service, db_session, sample_group, sample_user, sample_group_album):
        _set_threshold(db_session, sample_group.id, 1)
        sample_group_album.selected_date = datetime.now(tz=timezone.utc)
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=3))
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            participation_service.set_priority_pick(sample_group.id, sample_user.id, sample_group_album.id)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


class TestClaimPriorityPicks:
    def _pending_album(self, db_session, group, user, spotify_id, title):
        from app.models import Album

        album = Album(spotify_album_id=spotify_id, title=title, artist="A")
        db_session.add(album)
        db_session.commit()
        ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=user.id)
        db_session.add(ga)
        db_session.commit()
        db_session.refresh(ga)
        return ga

    def test_returns_empty_when_disabled(self, participation_service, db_session, sample_group):
        _set_threshold(db_session, sample_group.id, None)
        assert participation_service.claim_priority_picks(sample_group.id, 3) == []

    def test_fifo_order_and_debit(self, participation_service, db_session, sample_group, sample_user, user_factory):
        _set_threshold(db_session, sample_group.id, 2)
        u2 = user_factory(email="u2@test.com", username="u2")
        ga1 = self._pending_album(db_session, sample_group, sample_user, "sp1", "First")
        ga2 = self._pending_album(db_session, sample_group, u2, "sp2", "Second")

        now = datetime.now(tz=timezone.utc)
        # u2 queued earlier than sample_user → should come first (FIFO)
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=u2.id, credits=3,
            priority_group_album_id=ga2.id, priority_queued_at=now - timedelta(hours=1),
        ))
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, credits=5,
            priority_group_album_id=ga1.id, priority_queued_at=now,
        ))
        db_session.commit()

        claimed = participation_service.claim_priority_picks(sample_group.id, 5)
        db_session.commit()

        assert [ga.id for ga in claimed] == [ga2.id, ga1.id]
        # Surplus retained: credits reduced by threshold, not zeroed.
        assert participation_service.get_progress(sample_group.id, u2.id).credits == 1
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 3
        # Pending picks cleared.
        assert participation_service._get(sample_group.id, u2.id).priority_group_album_id is None

    def test_respects_limit(self, participation_service, db_session, sample_group, sample_user, user_factory):
        _set_threshold(db_session, sample_group.id, 2)
        u2 = user_factory(email="u2@test.com", username="u2")
        ga1 = self._pending_album(db_session, sample_group, sample_user, "sp1", "First")
        ga2 = self._pending_album(db_session, sample_group, u2, "sp2", "Second")
        now = datetime.now(tz=timezone.utc)
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, credits=5,
            priority_group_album_id=ga1.id, priority_queued_at=now - timedelta(hours=1),
        ))
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=u2.id, credits=5,
            priority_group_album_id=ga2.id, priority_queued_at=now,
        ))
        db_session.commit()

        claimed = participation_service.claim_priority_picks(sample_group.id, 1)
        assert [ga.id for ga in claimed] == [ga1.id]
        # The unclaimed pick is untouched.
        assert participation_service._get(sample_group.id, u2.id).priority_group_album_id == ga2.id

    def test_stale_pick_autocleared_not_returned(self, participation_service, db_session, sample_group, sample_user):
        _set_threshold(db_session, sample_group.id, 2)
        ga = self._pending_album(db_session, sample_group, sample_user, "sp1", "First")
        ga.selected_date = datetime.now(tz=timezone.utc)  # already selected → stale
        db_session.add(GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, credits=5,
            priority_group_album_id=ga.id, priority_queued_at=datetime.now(tz=timezone.utc),
        ))
        db_session.commit()

        claimed = participation_service.claim_priority_picks(sample_group.id, 3)
        db_session.commit()
        assert claimed == []
        row = participation_service._get(sample_group.id, sample_user.id)
        assert row.priority_group_album_id is None
        assert row.credits == 5  # not debited


class TestEndToEnd:
    """Full chain through the real services: review → credit → promote → draw → debit."""

    def _album(self, db_session, spotify_id, title):
        from app.models import Album

        album = Album(spotify_album_id=spotify_id, title=title, artist="Artist")
        db_session.add(album)
        db_session.commit()
        db_session.refresh(album)
        return album

    def _nominate(self, db_session, group, user, album):
        ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=user.id)
        db_session.add(ga)
        db_session.commit()
        db_session.refresh(ga)
        return ga

    def test_review_earns_credit_then_promote_then_draw(
        self,
        db_session,
        participation_service,
        review_service,
        group_album_service,
        sample_group,
        sample_user,
    ):
        from app.schemas.album import ReviewCreate

        _set_threshold(db_session, sample_group.id, 2)

        # Three nominations: the first two were drawn on a prior day (so reviewing
        # them earns credit), the third stays pending so it can be promoted.
        albums = [self._album(db_session, f"sp{i}", f"Album {i}") for i in range(3)]
        noms = [self._nominate(db_session, sample_group, sample_user, a) for a in albums]
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        for ga in noms[:2]:
            ga.selected_date = yesterday
        db_session.commit()

        # Publish two reviews in this group → two credits.
        for album in albums[:2]:
            review_service.create_review(
                album.id, sample_user.id, ReviewCreate(rating=8.0), group_id=sample_group.id
            )
        progress = participation_service.get_progress(sample_group.id, sample_user.id)
        assert progress.credits == 2
        assert progress.can_pick is True

        # Promote the third nomination.
        participation_service.set_priority_pick(sample_group.id, sample_user.id, noms[2].id)

        # The daily draw renders the promoted album (n=1 → priority occupies the slot).
        results = group_album_service.select_daily_albums(sample_group.id, n=1)
        assert [ga.album_id for ga in results] == [albums[2].id]

        # Credit debited by the threshold; pick cleared.
        final = participation_service.get_progress(sample_group.id, sample_user.id)
        assert final.credits == 0
        assert final.pending_pick is None

    def test_draft_publish_awards_once(
        self, db_session, participation_service, review_service, sample_group, sample_user
    ):
        from app.schemas.album import ReviewCreate, ReviewUpdate

        _set_threshold(db_session, sample_group.id, 5)
        album = self._album(db_session, "spd", "Draft Album")
        ga = self._nominate(db_session, sample_group, sample_user, album)
        ga.selected_date = datetime.now(tz=timezone.utc)  # drawn → credit-eligible
        db_session.commit()

        # Create as draft (no credit yet), then publish via update (one credit).
        review = review_service.create_review(
            album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True), group_id=sample_group.id
        )
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 0

        review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(is_draft=False), group_id=sample_group.id
        )
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1

        # Editing the already-published review does not re-award.
        review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(comment="edited"), group_id=sample_group.id
        )
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1


class TestCreditExistingReviewers:
    """Members who already reviewed an album earn credit when it is drawn into the group."""

    def _album(self, db_session, spotify_id, title):
        from app.models import Album

        album = Album(spotify_album_id=spotify_id, title=title, artist="Artist")
        db_session.add(album)
        db_session.commit()
        db_session.refresh(album)
        return album

    def test_prior_reviewer_credited_on_draw(
        self, db_session, participation_service, group_album_service, sample_group, sample_user
    ):
        _set_threshold(db_session, sample_group.id, 2)
        album = self._album(db_session, "spx", "Prior")
        # The member reviewed the album BEFORE it entered the group.
        _make_review(db_session, sample_user, album)
        _nominate(db_session, sample_group, sample_user, album)

        # No credit yet — the album was only just nominated, not drawn.
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 0

        group_album_service.select_daily_albums(sample_group.id, n=1)

        # The draw backfills the credit for the pre-existing review.
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 1

    def test_draft_reviewer_not_credited_on_draw(
        self, db_session, participation_service, group_album_service, sample_group, sample_user
    ):
        _set_threshold(db_session, sample_group.id, 2)
        album = self._album(db_session, "spd", "Draft")
        _make_review(db_session, sample_user, album, is_draft=True)  # unpublished
        _nominate(db_session, sample_group, sample_user, album)

        group_album_service.select_daily_albums(sample_group.id, n=1)

        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 0

    def test_no_double_credit_across_review_and_draw(
        self, db_session, participation_service, review_service, group_album_service, sample_group, sample_user
    ):
        """Reviewing a pending album then having it drawn grants exactly one credit."""
        from app.schemas.album import ReviewCreate

        _set_threshold(db_session, sample_group.id, 2)
        album = self._album(db_session, "spo", "Once")
        _nominate(db_session, sample_group, sample_user, album)

        # Reviewing a not-yet-drawn nomination earns nothing at review time.
        review_service.create_review(
            album.id, sample_user.id, ReviewCreate(rating=8.0), group_id=sample_group.id
        )
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 0

        # The draw backfills the single credit, and must not double-count.
        group_album_service.select_daily_albums(sample_group.id, n=1)
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1
        assert _ledger_count(db_session, sample_group.id, sample_user.id) == 1

    def test_one_review_credits_multiple_groups(
        self, db_session, participation_service, group_album_service, sample_group, sample_user, group_factory
    ):
        """A single review earns a credit in every group its album is drawn into."""
        album = self._album(db_session, "spm", "Shared")
        _make_review(db_session, sample_user, album)

        _set_threshold(db_session, sample_group.id, 2)
        _nominate(db_session, sample_group, sample_user, album)
        group_album_service.select_daily_albums(sample_group.id, n=1)
        assert participation_service.get_progress(sample_group.id, sample_user.id).credits == 1

        # A second group the same member belongs to also draws the album.
        group2 = group_factory(name="Second", user=sample_user)
        _set_threshold(db_session, group2.id, 2)
        _nominate(db_session, group2, sample_user, album)
        group_album_service.select_daily_albums(group2.id, n=1)
        assert participation_service.get_progress(group2.id, sample_user.id).credits == 1
