"""GroupAlbum workflow service: daily selection, guessing, and instant nomination reveal.

Selection lifecycle (driven by cron, not admin action):
  - selected_date IS NULL  → available for future selection
  - selected_date IS NOT NULL → selected on that date (historical / today's spin)

Guess lifecycle (per-user, instant feedback):
  - Member submits guess → immediately receives correct/incorrect + nominator identity
"""

import random
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import GroupAlbum, NominationGuess, User
from app.schemas.group_album import CheckGuessResponse, NominationGuessCreate, NominationGuessResponse
from app.services import group_service as gs


class GroupAlbumService:
    """Workflow service for the nomination → daily-selection → guess lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== DAILY SELECTION (cron-driven) ====================

    def select_daily_albums(self, group_id: int, n: int = 1) -> list[GroupAlbum]:
        """Randomly select N unselected albums as today's daily spins for a group.

        Operates on distinct albums — if multiple members nominated the same album,
        it counts as one candidate and all their nominations are marked selected together.
        Returns one canonical GroupAlbum (earliest nomination) per selected album.

        Raises:
            HTTPException 409: If fewer than N eligible distinct albums are available.
        """
        available_album_ids = [
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.is_(None))
            .distinct()
            .all()
        ]
        if len(available_album_ids) < n:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Not enough unselected albums: need {n}, have {len(available_album_ids)}",
            )

        chosen_album_ids = random.sample(available_album_ids, n)
        now = datetime.now(tz=timezone.utc)

        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id.in_(chosen_album_ids),
                GroupAlbum.selected_date.is_(None),
            )
            .all()
        )
        for ga in all_nominations:
            ga.selected_date = now

        self.db.commit()

        # Return the canonical (earliest) nomination per selected album
        canonical: dict[int, GroupAlbum] = {}
        for ga in all_nominations:
            self.db.refresh(ga)
            if ga.album_id not in canonical or ga.id < canonical[ga.album_id].id:
                canonical[ga.album_id] = ga
        return list(canonical.values())

    def get_todays_albums(self, group_id: int, user: User) -> list[GroupAlbum]:
        """Return albums selected as today's daily spins for a group. Requires membership.

        When an album has multiple nominations they are all selected together;
        this returns one canonical GroupAlbum (earliest nomination) per album.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        today = date.today()
        all_today = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                func.date(GroupAlbum.selected_date) == today,
            )
            .order_by(GroupAlbum.id)
            .all()
        )

        # Deduplicate by album_id, keeping the canonical (lowest id) row
        seen: set[int] = set()
        canonical = []
        for ga in all_today:
            if ga.album_id not in seen:
                seen.add(ga.album_id)
                canonical.append(ga)
        return canonical

    # ==================== GUESSING ====================

    def check_guess(
        self, group_id: int, group_album_id: int, user: User, data: NominationGuessCreate
    ) -> CheckGuessResponse:
        """Submit a nomination guess and receive instant feedback.

        Rules:
        - Album must have been selected (selected_date IS NOT NULL).
        - User must be a group member.
        - User cannot guess themselves.
        - One guess per user per album (409 on duplicate).

        Returns the stored guess plus whether it was correct and the actual nominator.

        Raises:
            HTTPException 403: If user is not a member or guesses themselves.
            HTTPException 409: If album has not been selected or guess already submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.selected_date is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guesses can only be submitted for albums that have been selected",
            )

        if data.guessed_user_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot guess yourself as the nominator",
            )

        # Collect all nominators for this album in this group
        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == group_album.album_id,
            )
            .all()
        )
        nominator_ids = {ga.added_by for ga in all_nominations}
        correct = data.guessed_user_id in nominator_ids

        guess = NominationGuess(
            group_album_id=group_album_id,
            guessing_user_id=user.id,
            guessed_user_id=data.guessed_user_id,
            correct=correct,
        )
        try:
            self.db.add(guess)
            self.db.flush()
        except IntegrityError as e:
            self.db.rollback()
            # Distinguish duplicate-guess from other constraint violations
            if "unique_guess_per_user_album" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already submitted a guess for this album",
                ) from None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guess could not be saved due to a constraint violation",
            ) from None

        self.db.commit()
        self.db.refresh(guess)

        nominators = [ga.added_by_user for ga in all_nominations]

        return CheckGuessResponse(
            guess=NominationGuessResponse.model_validate(guess),
            correct=correct,
            nominator_user_ids=[n.id for n in nominators],
            nominator_usernames=[n.username for n in nominators],
        )

    def get_my_guess(self, group_id: int, group_album_id: int, user: User) -> CheckGuessResponse:
        """Get the current user's prior guess for a group album, including nominator details.

        Returns the same shape as check_guess so callers always get nominator context.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If no guess has been submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)
        group_album = self._get_group_album_or_404(group_id, group_album_id)
        guess = self._get_guess(group_album_id, user.id, raise_on_missing=True)

        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == group_album.album_id,
            )
            .all()
        )
        nominators = [ga.added_by_user for ga in all_nominations]

        return CheckGuessResponse(
            guess=NominationGuessResponse.model_validate(guess),
            correct=guess.correct,
            nominator_user_ids=[n.id for n in nominators],
            nominator_usernames=[n.username for n in nominators],
        )

    # ==================== HELPERS ====================

    def _get_group_album_or_404(self, group_id: int, group_album_id: int) -> GroupAlbum:
        ga = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.id == group_album_id, GroupAlbum.group_id == group_id)
            .first()
        )
        if not ga:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group album {group_album_id} not found in group {group_id}",
            )
        return ga

    def _get_guess(
        self, group_album_id: int, user_id: int, *, raise_on_missing: bool = False
    ) -> NominationGuess | None:
        guess = (
            self.db.query(NominationGuess)
            .filter(
                NominationGuess.group_album_id == group_album_id,
                NominationGuess.guessing_user_id == user_id,
            )
            .first()
        )
        if not guess and raise_on_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No guess found for this album",
            )
        return guess
