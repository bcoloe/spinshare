"""Review service."""

from app.models import Review
from app.schemas.album import ReviewCreate, ReviewUpdate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class ReviewService:
    """Service layer for Review operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_review(self, album_id: int, user_id: int, data: ReviewCreate) -> Review:
        """Create a review for an album.

        Raises:
            HTTPException 409: If user already reviewed this album.
        """
        review = Review(
            album_id=album_id,
            user_id=user_id,
            rating=data.rating,
            comment=data.comment,
        )
        try:
            self.db.add(review)
            self.db.commit()
            self.db.refresh(review)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already reviewed this album",
            ) from None
        return review

    # ==================== GET ====================

    def get_review_by_id(self, review_id: int) -> Review:
        """Get a review by ID.

        Raises:
            HTTPException 404: If review not found.
        """
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review {review_id} not found",
            )
        return review

    def get_reviews_for_album(self, album_id: int) -> list[Review]:
        """Return all reviews for a given album."""
        return self.db.query(Review).filter(Review.album_id == album_id).all()

    def get_review_by_user_and_album(
        self, album_id: int, user_id: int, *, raise_on_missing: bool = True
    ) -> Review | None:
        """Return a user's review for a specific album.

        Raises:
            HTTPException 404: If raise_on_missing=True and review not found.
        """
        review = (
            self.db.query(Review)
            .filter(Review.album_id == album_id, Review.user_id == user_id)
            .first()
        )
        if not review and raise_on_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No review found for this album",
            )
        return review

    # ==================== UPDATE ====================

    def update_review(self, review_id: int, user_id: int, data: ReviewUpdate) -> Review:
        """Update an existing review. Only the author may update.

        Raises:
            HTTPException 403: If user is not the review author.
            HTTPException 404: If review not found.
        """
        review = self.get_review_by_id(review_id)
        if review.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own reviews",
            )

        if data.rating is not None:
            review.rating = data.rating
        if data.comment is not None:
            review.comment = data.comment

        self.db.commit()
        self.db.refresh(review)
        return review

    # ==================== DELETE ====================

    def delete_review(self, review_id: int, user_id: int):
        """Delete a review. Only the author may delete.

        Raises:
            HTTPException 403: If user is not the review author.
            HTTPException 404: If review not found.
        """
        review = self.get_review_by_id(review_id)
        if review.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own reviews",
            )
        self.db.delete(review)
        self.db.commit()
