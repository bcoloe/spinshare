"""Stats service: guess accuracy and review score aggregations."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import GroupAlbum, NominationGuess, Review
from app.schemas.stats import (
    AlbumGuessStatsResponse,
    AlbumReviewStatsResponse,
    MemberGuessResult,
    UserGuessStatsResponse,
)
from app.services import group_service as gs
from fastapi import HTTPException, status


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== GUESS ACCURACY ====================

    def get_user_guess_stats(self, user_id: int, group_id: int) -> UserGuessStatsResponse:
        """Guess accuracy for a user within a specific group.

        Raises:
            HTTPException 403: If requesting user is not a member (caller must enforce).
            HTTPException 404: If user has no guesses in this group.
        """
        rows = (
            self.db.query(NominationGuess)
            .join(GroupAlbum, NominationGuess.group_album_id == GroupAlbum.id)
            .filter(
                NominationGuess.guessing_user_id == user_id,
                GroupAlbum.group_id == group_id,
            )
            .all()
        )

        total = len(rows)
        correct = sum(1 for r in rows if r.correct)
        accuracy = (correct / total) if total > 0 else 0.0

        return UserGuessStatsResponse(
            user_id=user_id,
            group_id=group_id,
            total_guesses=total,
            correct_guesses=correct,
            accuracy=accuracy,
        )

    def get_album_guess_stats(self, group_id: int, group_album_id: int) -> AlbumGuessStatsResponse:
        """Per-member guess breakdown for a specific group album.

        Raises:
            HTTPException 404: If group album not found.
        """
        group_album = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.id == group_album_id, GroupAlbum.group_id == group_id)
            .first()
        )
        if not group_album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group album {group_album_id} not found in group {group_id}",
            )

        guesses = [
            MemberGuessResult(
                guessing_user_id=g.guessing_user_id,
                guessing_username=g.guessing_user.username,
                guessed_user_id=g.guessed_user_id,
                guessed_username=g.guessed_user.username,
                correct=g.correct,
            )
            for g in group_album.guesses
        ]

        total = len(guesses)
        correct = sum(1 for g in guesses if g.correct)
        nominator = group_album.added_by_user

        return AlbumGuessStatsResponse(
            group_album_id=group_album_id,
            nominator_user_id=nominator.id,
            nominator_username=nominator.username,
            total_guesses=total,
            correct_guesses=correct,
            guesses=guesses,
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
