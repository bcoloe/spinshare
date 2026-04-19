"""GroupAlbum workflow service: selection, guessing, and nomination reveal."""

import random

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import GroupAlbum, NominationGuess, User
from app.models.group import GroupRole
from app.schemas.group_album import (
    GuessResultResponse,
    NominationGuessCreate,
    NominationRevealResponse,
    SelectAlbumRequest,
)
from app.services import group_service as gs


class GroupAlbumService:
    """Workflow service for the nomination → selection → review lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== SELECTION ====================

    def select_album(
        self, group_id: int, user: User, request: SelectAlbumRequest
    ) -> GroupAlbum:
        """Select an album as the group's active daily spin. Requires Admin or Owner.

        If request.group_album_id is provided, that specific album is selected.
        Otherwise a random pending album is chosen.

        Only one album may be in 'selected' status per group at a time; any
        currently-selected album is returned to 'pending' before the new one is set.

        Raises:
            HTTPException 403: If user is not Admin or Owner.
            HTTPException 404: If the specified group_album_id is not found.
            HTTPException 409: If there are no pending albums to select from.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_permission(user.id, group_id, GroupRole.Admin)

        # Clear any currently selected album back to pending.
        current = self._get_selected(group_id)
        if current:
            current.status = "pending"

        if request.group_album_id is not None:
            target = self._get_group_album_or_404(group_id, request.group_album_id)
            if target.status != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Album {request.group_album_id} is not in pending status",
                )
        else:
            pending = (
                self.db.query(GroupAlbum)
                .filter(GroupAlbum.group_id == group_id, GroupAlbum.status == "pending")
                .all()
            )
            if not pending:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No pending albums available to select",
                )
            target = random.choice(pending)

        target.status = "selected"
        self.db.commit()
        self.db.refresh(target)
        return target

    def get_selected_album(self, group_id: int, user: User) -> GroupAlbum:
        """Return the currently selected album for a group. Requires membership.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If no album is currently selected.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        album = self._get_selected(group_id)
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No album is currently selected for this group",
            )
        return album

    # ==================== GUESSING ====================

    def submit_guess(
        self, group_id: int, group_album_id: int, user: User, data: NominationGuessCreate
    ) -> NominationGuess:
        """Submit a guess for who nominated the currently selected album.

        Rules:
        - Album must be in 'selected' status.
        - User must be a group member.
        - User cannot guess themselves as the nominator.
        - One guess per user per group album (409 on duplicate).

        Raises:
            HTTPException 403: If user is not a member or guesses themselves.
            HTTPException 409: If album is not selected or guess already submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.status != "selected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guesses can only be submitted while the album is in 'selected' status",
            )

        if data.guessed_user_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot guess yourself as the nominator",
            )

        guess = NominationGuess(
            group_album_id=group_album_id,
            guessing_user_id=user.id,
            guessed_user_id=data.guessed_user_id,
        )
        try:
            self.db.add(guess)
            self.db.commit()
            self.db.refresh(guess)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted a guess for this album",
            ) from None
        return guess

    def update_guess(
        self, group_id: int, group_album_id: int, user: User, data: NominationGuessCreate
    ) -> NominationGuess:
        """Update an existing guess while the album is still in 'selected' status.

        Raises:
            HTTPException 403: If user guesses themselves.
            HTTPException 404: If no prior guess exists.
            HTTPException 409: If album is not in 'selected' status.
        """
        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.status != "selected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guesses can only be updated while the album is in 'selected' status",
            )

        if data.guessed_user_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot guess yourself as the nominator",
            )

        guess = self._get_guess(group_album_id, user.id, raise_on_missing=True)
        guess.guessed_user_id = data.guessed_user_id
        self.db.commit()
        self.db.refresh(guess)
        return guess

    def get_my_guess(self, group_id: int, group_album_id: int, user: User) -> NominationGuess:
        """Get the current user's guess for a group album.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If no guess has been submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)
        self._get_group_album_or_404(group_id, group_album_id)
        return self._get_guess(group_album_id, user.id, raise_on_missing=True)

    # ==================== REVIEW PHASE ====================

    def complete_review_phase(
        self, group_id: int, group_album_id: int, user: User
    ) -> GroupAlbum:
        """Transition a selected album to 'reviewed', unlocking the nomination reveal.
        Requires Admin or Owner.

        Raises:
            HTTPException 403: If user is not Admin or Owner.
            HTTPException 409: If album is not currently in 'selected' status.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_permission(user.id, group_id, GroupRole.Admin)

        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.status != "selected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only albums in 'selected' status can be moved to 'reviewed'",
            )

        group_album.status = "reviewed"
        self.db.commit()
        self.db.refresh(group_album)
        return group_album

    # ==================== REVEAL ====================

    def reveal_nominator(
        self, group_id: int, group_album_id: int, user: User
    ) -> NominationRevealResponse:
        """Reveal who nominated the album and show each member's guess accuracy.

        Only available once the album reaches 'reviewed' status.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 409: If album has not yet been reviewed.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.status != "reviewed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nomination reveal is only available after the review phase is complete",
            )

        nominator = group_album.added_by_user
        guesses = group_album.guesses

        guess_results = [
            GuessResultResponse(
                guessing_user_id=g.guessing_user_id,
                guessing_username=g.guessing_user.username,
                guessed_user_id=g.guessed_user_id,
                guessed_username=g.guessed_user.username,
                correct=g.guessed_user_id == group_album.added_by,
            )
            for g in guesses
        ]

        return NominationRevealResponse(
            group_album_id=group_album_id,
            nominator_user_id=nominator.id,
            nominator_username=nominator.username,
            guesses=guess_results,
        )

    # ==================== HELPERS ====================

    def _get_selected(self, group_id: int) -> GroupAlbum | None:
        return (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.status == "selected")
            .first()
        )

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
