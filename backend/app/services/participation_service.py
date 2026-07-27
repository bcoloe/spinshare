"""Priority-pick participation service.

Members earn a credit each time they publish a new review in a standard
(shared-draw) group. Once their credit balance reaches the group's configurable
``priority_pick_threshold`` they may promote one of their own pending
nominations, which the next daily draw selects ahead of the random picks. When
that album is drawn the balance is reduced by the threshold (surplus carries
forward). See ``plans/harmonic-juggling-neumann.md``.

The feature is standard-groups-only: it is inert for the global group and for
dealer-mode groups (which have no shared draw to render a pick).
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Group,
    GroupAlbum,
    GroupParticipation,
    GroupSettings,
    PriorityReviewCredit,
    Review,
)
from app.models.group import group_members
from app.schemas.album import GroupAlbumResponse
from app.schemas.participation import ParticipationResponse
from app.services import group_service as gs


class ParticipationService:
    """Business logic for review credits and priority picks."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== EARNING ====================

    def award_review_credit(self, group_id: int, user_id: int, review: Review) -> None:
        """Grant a participation credit for a newly published review.

        Called from the review-publish paths. No-op unless the feature is active,
        the reviewer is a member, and the reviewed album belongs to the group.
        Idempotent per (group, user, album) via the credit ledger. Commits on award.
        """
        self._grant_credit(group_id, user_id, review.album_id, commit=True)

    def credit_existing_reviewers(self, group_id: int, album_ids: list[int]) -> None:
        """Credit members who already reviewed an album that was just drawn into the group.

        Called after a daily draw. A member who reviewed the album before it entered
        the group will never review it again, so the review-publish hook cannot fire
        for them — this backfills their credit. No-op when the feature is disabled.
        Idempotent via the ledger; commits once at the end.
        """
        threshold = self._feature_threshold(group_id)
        if threshold is None or not album_ids:
            return

        member_ids = set(
            self.db.scalars(
                select(group_members.c.user_id).where(group_members.c.group_id == group_id)
            ).all()
        )
        if not member_ids:
            return

        reviewer_album_pairs = self.db.execute(
            select(Review.user_id, Review.album_id).where(
                Review.album_id.in_(album_ids),
                Review.user_id.in_(member_ids),
                Review.is_draft == False,  # noqa: E712
            )
        ).all()
        for user_id, album_id in reviewer_album_pairs:
            self._grant_credit(group_id, user_id, album_id, commit=False)
        self.db.commit()

    def _grant_credit(self, group_id: int, user_id: int, album_id: int, *, commit: bool) -> None:
        """Grant one credit for (group, user, album) if not already granted.

        Guards: feature active, user is a member, and the album belongs to the group.
        The ledger row makes this idempotent — a review can earn a credit in every
        group its album belongs to, but never twice within one group.
        """
        threshold = self._feature_threshold(group_id)
        if threshold is None:
            return
        if not gs.GroupService(self.db).is_user_in_group(user_id, group_id):
            return
        album_in_group = (
            self.db.query(GroupAlbum.id)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.album_id == album_id)
            .first()
        )
        if album_in_group is None:
            return
        already_credited = (
            self.db.query(PriorityReviewCredit.id)
            .filter(
                PriorityReviewCredit.group_id == group_id,
                PriorityReviewCredit.user_id == user_id,
                PriorityReviewCredit.album_id == album_id,
            )
            .first()
        )
        if already_credited is not None:
            return

        self.db.add(
            PriorityReviewCredit(group_id=group_id, user_id=user_id, album_id=album_id)
        )
        participation = self._get_or_create(group_id, user_id)
        participation.credits += self._review_credit_amount(group_id, user_id, album_id)
        if commit:
            self.db.commit()

    def _review_credit_amount(self, group_id: int, user_id: int, album_id: int) -> int:
        """Credits granted for a single review. Flat +1 today.

        Isolated so a future streak multiplier (e.g. double credits for reviews on
        consecutive days, computable from the member's ``Review.reviewed_at``) can
        hook in here without touching callers or the schema.
        """
        return 1

    # ==================== READS ====================

    def get_progress(self, group_id: int, user_id: int) -> ParticipationResponse:
        """Return the caller's priority-pick standing in the group.

        ``threshold`` is None when the feature is disabled (global/dealer/unset),
        in which case credits are reported as 0 and no pick can be made.
        """
        threshold = self._feature_threshold(group_id)
        if threshold is None:
            return ParticipationResponse(threshold=None, credits=0, can_pick=False)

        participation = self._get(group_id, user_id)
        credits = participation.credits if participation else 0
        pending = (
            participation.priority_group_album
            if participation and participation.priority_group_album_id is not None
            else None
        )
        return ParticipationResponse(
            threshold=threshold,
            credits=credits,
            can_pick=(credits >= threshold and pending is None),
            pending_pick=GroupAlbumResponse.from_orm(pending) if pending is not None else None,
        )

    # ==================== PROMOTING ====================

    def set_priority_pick(
        self, group_id: int, user_id: int, group_album_id: int
    ) -> ParticipationResponse:
        """Promote one of the caller's pending nominations to the front of the line.

        Raises:
            HTTPException 403: Caller is not a group member.
            HTTPException 409 "priority_pick_disabled": Feature not enabled here.
            HTTPException 409 "insufficient_credits": Balance below the threshold.
            HTTPException 409 "pick_already_queued": A pick is already standing.
            HTTPException 404: The album is not a pending nomination the caller added.
        """
        gs.GroupService(self.db).require_membership(user_id, group_id)

        threshold = self._feature_threshold(group_id)
        if threshold is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="priority_pick_disabled"
            )

        participation = self._get(group_id, user_id)
        credits = participation.credits if participation else 0
        if credits < threshold:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="insufficient_credits"
            )
        if participation is not None and participation.priority_group_album_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="pick_already_queued"
            )

        group_album = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.id == group_album_id,
                GroupAlbum.group_id == group_id,
                GroupAlbum.added_by == user_id,
                GroupAlbum.selected_date.is_(None),
            )
            .first()
        )
        if group_album is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending nomination of yours matches that album",
            )

        participation = participation or self._get_or_create(group_id, user_id)
        participation.priority_group_album_id = group_album.id
        participation.priority_queued_at = datetime.now(tz=timezone.utc)
        self.db.commit()
        return self.get_progress(group_id, user_id)

    # ==================== DRAW HOOK ====================

    def claim_priority_picks(self, group_id: int, limit: int) -> list[GroupAlbum]:
        """Consume up to ``limit`` queued priority picks for the group's daily draw.

        Returns the promoted ``GroupAlbum`` rows (FIFO by queue time) for the caller
        to mark selected. For each claimed pick the owner's balance is debited by the
        threshold and the pick fields cleared. Stale picks (album gone or already
        selected) are auto-cleared without being returned, freeing that member to
        promote again. Does not commit — runs inside the draw's transaction.
        """
        threshold = self._feature_threshold(group_id)
        if threshold is None or limit <= 0:
            return []

        candidates = (
            self.db.query(GroupParticipation)
            .filter(
                GroupParticipation.group_id == group_id,
                GroupParticipation.priority_group_album_id.isnot(None),
            )
            .order_by(GroupParticipation.priority_queued_at)
            .all()
        )

        claimed: list[GroupAlbum] = []
        for participation in candidates:
            group_album = (
                self.db.query(GroupAlbum)
                .filter(
                    GroupAlbum.id == participation.priority_group_album_id,
                    GroupAlbum.group_id == group_id,
                )
                .first()
            )
            if group_album is None or group_album.selected_date is not None:
                # Stale promotion — free the slot so the member can pick again.
                participation.priority_group_album_id = None
                participation.priority_queued_at = None
                continue

            participation.credits = max(0, participation.credits - threshold)
            participation.priority_group_album_id = None
            participation.priority_queued_at = None
            claimed.append(group_album)
            if len(claimed) >= limit:
                break
        return claimed

    # ==================== HELPERS ====================

    def _feature_threshold(self, group_id: int) -> int | None:
        """The active priority-pick threshold for the group, or None if disabled.

        Disabled when: no settings row, threshold unset/zero, dealer mode on, or the
        group is the global group.
        """
        settings = (
            self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        )
        if settings is None or settings.dealer_mode or not settings.priority_pick_threshold:
            return None
        is_global = self.db.query(Group.is_global).filter(Group.id == group_id).scalar()
        if is_global:
            return None
        return settings.priority_pick_threshold

    def _get(self, group_id: int, user_id: int) -> GroupParticipation | None:
        return (
            self.db.query(GroupParticipation)
            .filter(
                GroupParticipation.group_id == group_id,
                GroupParticipation.user_id == user_id,
            )
            .first()
        )

    def _get_or_create(self, group_id: int, user_id: int) -> GroupParticipation:
        participation = self._get(group_id, user_id)
        if participation is None:
            participation = GroupParticipation(group_id=group_id, user_id=user_id, credits=0)
            self.db.add(participation)
            self.db.flush()
        return participation
