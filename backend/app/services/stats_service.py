"""Stats service: guess accuracy and review score aggregations."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased, joinedload

from app.models import GroupAlbum, NominationGuess, Review, User
from app.schemas.stats import (
    AlbumGuessStatsResponse,
    AlbumReviewStatsResponse,
    MemberGuessResult,
    UserGuessStatsResponse,
)
from fastapi import HTTPException, status


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== GUESS ACCURACY ====================

    def get_user_guess_stats(self, user_id: int, group_id: int) -> UserGuessStatsResponse:
        """Guess accuracy for a user within a specific group.

        Membership is enforced at the route (see ``require_group_role``), so this
        method assumes the caller is already authorized.

        Raises:
            HTTPException 404: If user has no guesses in this group.
        """
        # Counted in the database (same shape as RecapService._guess_accuracy)
        # rather than hydrating every guess row just to len() and filter it.
        correct_case = case((NominationGuess.correct.is_(True), 1), else_=0)
        total, correct = (
            self.db.query(
                func.count(NominationGuess.id),
                func.coalesce(func.sum(correct_case), 0),
            )
            .join(GroupAlbum, NominationGuess.group_album_id == GroupAlbum.id)
            .filter(
                NominationGuess.guessing_user_id == user_id,
                GroupAlbum.group_id == group_id,
            )
            .one()
        )

        accuracy = (correct / total) if total > 0 else 0.0

        return UserGuessStatsResponse(
            user_id=user_id,
            group_id=group_id,
            total_guesses=total,
            correct_guesses=correct,
            accuracy=accuracy,
        )

    def get_album_guess_stats(
        self, group_id: int, group_album_id: int, viewer_id: int
    ) -> AlbumGuessStatsResponse:
        """Per-member guess breakdown for a specific group album.

        Results are withheld until the viewer's own guess is settled — that is,
        until they have submitted a guess or are the nominator (and so cannot
        guess). Otherwise the breakdown would hand them the answer.

        Raises:
            HTTPException 404: If group album not found.
        """
        group_album = (
            self.db.query(GroupAlbum)
            # The nominator is read below for every revealed response; joining it
            # here costs nothing extra and removes a lazy load.
            .options(joinedload(GroupAlbum.added_by_user))
            .filter(GroupAlbum.id == group_album_id, GroupAlbum.group_id == group_id)
            .first()
        )
        if not group_album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group album {group_album_id} not found in group {group_id}",
            )

        if not self._guesses_revealed_to(group_album, viewer_id):
            return AlbumGuessStatsResponse(
                group_album_id=group_album_id,
                nominator_user_id=None,
                nominator_username=None,
                total_guesses=0,
                correct_guesses=0,
                guesses=[],
                revealed=False,
            )

        # Only the two usernames are needed per guess, so they are joined in
        # rather than lazy-loaded off each guess: the relationship walk cost two
        # extra round trips per guess (one per User row) for one string each.
        guessing_user = aliased(User)
        guessed_user = aliased(User)
        rows = self.db.execute(
            select(
                NominationGuess.guessing_user_id,
                guessing_user.username,
                NominationGuess.guessed_user_id,
                guessed_user.username,
                NominationGuess.correct,
            )
            .join(guessing_user, guessing_user.id == NominationGuess.guessing_user_id)
            .outerjoin(guessed_user, guessed_user.id == NominationGuess.guessed_user_id)
            .where(NominationGuess.group_album_id == group_album_id)
            .order_by(NominationGuess.id)
        ).all()

        guesses = [
            MemberGuessResult(
                guessing_user_id=guessing_user_id,
                guessing_username=guessing_username,
                guessed_user_id=guessed_user_id,
                guessed_username=guessed_username if guessed_user_id is not None else None,
                is_chaos=guessed_user_id is None,
                correct=correct_flag,
            )
            for (
                guessing_user_id,
                guessing_username,
                guessed_user_id,
                guessed_username,
                correct_flag,
            ) in rows
        ]

        total = len(guesses)
        correct = sum(1 for g in guesses if g.correct)
        nominator = group_album.added_by_user

        return AlbumGuessStatsResponse(
            group_album_id=group_album_id,
            nominator_user_id=nominator.id if nominator else None,
            nominator_username=nominator.username if nominator else None,
            total_guesses=total,
            correct_guesses=correct,
            guesses=guesses,
            revealed=True,
        )

    def _guesses_revealed_to(self, group_album: GroupAlbum, viewer_id: int) -> bool:
        """Whether this album's guesses may be shown to ``viewer_id``.

        True once the viewer can no longer be given an unfair advantage: they
        have already guessed, or they nominated the album and so are barred
        from guessing it.
        """
        if group_album.added_by == viewer_id:
            return True

        return (
            self.db.query(NominationGuess.id)
            .filter(
                NominationGuess.group_album_id == group_album.id,
                NominationGuess.guessing_user_id == viewer_id,
            )
            .first()
            is not None
        )

    # ==================== REVIEW SCORES ====================

    def get_album_review_stats(self, album_id: int) -> AlbumReviewStatsResponse:
        """Aggregate review score stats for an album across all groups.

        Raises:
            HTTPException 404: If no reviews exist for this album.
        """
        row = (
            self.db.query(
                func.count(Review.id).label("review_count"),
                func.avg(Review.rating).label("avg_rating"),
                func.min(Review.rating).label("min_rating"),
                func.max(Review.rating).label("max_rating"),
            )
            .filter(Review.album_id == album_id)
            .one()
        )

        if row.review_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No reviews found for album {album_id}",
            )

        return AlbumReviewStatsResponse(
            album_id=album_id,
            review_count=row.review_count,
            avg_rating=round(float(row.avg_rating), 2),
            min_rating=float(row.min_rating),
            max_rating=float(row.max_rating),
        )
