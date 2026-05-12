"""Review service."""

from app.models import Album, Group, GroupAlbum, Review, User, group_members
from app.schemas.album import AlbumReviewItem, AlbumStatsResponse, HistogramBucket, ReviewCreate, ReviewUpdate
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService
from fastapi import HTTPException, status
from sqlalchemy import select
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
            is_draft=data.is_draft,
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
        if not data.is_draft:
            self._notify_co_reviewers(album_id, user_id)
        return review

    def _notify_co_reviewers(self, album_id: int, reviewer_id: int) -> None:
        """Notify group members who already reviewed this album that a new review was posted.

        Only fires for non-global groups; one notification per (member, group) pair.
        """
        album = self.db.get(Album, album_id)
        reviewer = self.db.get(User, reviewer_id)
        if not album or not reviewer:
            return

        groups_with_album = (
            self.db.scalars(
                select(GroupAlbum)
                .join(Group, GroupAlbum.group_id == Group.id)
                .where(GroupAlbum.album_id == album_id, Group.is_global == False)  # noqa: E712
            ).all()
        )

        ns = NotificationService(self.db)
        for ga in groups_with_album:
            member_ids = list(
                self.db.scalars(
                    select(group_members.c.user_id).where(group_members.c.group_id == ga.group_id)
                ).all()
            )
            co_reviewer_ids = list(
                self.db.scalars(
                    select(Review.user_id).where(
                        Review.album_id == album_id,
                        Review.user_id.in_(member_ids),
                        Review.user_id != reviewer_id,
                        Review.is_draft == False,  # noqa: E712
                    )
                ).all()
            )
            for uid in co_reviewer_ids:
                ns.create(
                    user_id=uid,
                    type=NotificationType.member_reviewed_album,
                    message=f"{reviewer.username} also reviewed {album.title}",
                    group_id=ga.group_id,
                )

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

    def get_reviews_for_album(
        self, album_id: int, viewer_id: int | None = None, group_id: int | None = None
    ) -> list[AlbumReviewItem]:
        """Return all published (non-draft) reviews for a given album, including reviewer usernames.

        Names are shown when:
        - The reviewer has name_is_public=True, OR
        - A group_id is provided, the viewer is a member, and the group is not global.
        """
        show_names_in_group = False
        if group_id is not None and viewer_id is not None:
            group = self.db.query(Group).filter(Group.id == group_id).first()
            if group and not group.is_global:
                is_member = self.db.execute(
                    select(group_members).where(
                        group_members.c.group_id == group_id,
                        group_members.c.user_id == viewer_id,
                    )
                ).first()
                show_names_in_group = is_member is not None

        rows = (
            self.db.query(Review, User.username, User.first_name, User.last_name, User.name_is_public)
            .join(User, Review.user_id == User.id)
            .filter(Review.album_id == album_id, Review.is_draft == False)  # noqa: E712
            .all()
        )
        return [
            AlbumReviewItem(
                id=r.id,
                album_id=r.album_id,
                user_id=r.user_id,
                username=username,
                first_name=first_name if (name_is_public or show_names_in_group) else None,
                last_name=last_name if (name_is_public or show_names_in_group) else None,
                rating=r.rating,
                comment=r.comment,
                is_draft=r.is_draft,
                reviewed_at=r.reviewed_at,
                updated_at=r.updated_at,
            )
            for r, username, first_name, last_name, name_is_public in rows
        ]

    def get_album_stats(self, album_id: int) -> AlbumStatsResponse:
        """Return global rating stats and a 10-bucket histogram for an album.

        Buckets span [0,1), [1,2), ..., [8,9), [9,10] (last bucket is inclusive on both ends).
        Draft reviews and unrated reviews are excluded.
        """
        reviews = (
            self.db.query(Review)
            .filter(
                Review.album_id == album_id,
                Review.is_draft == False,  # noqa: E712
                Review.rating.isnot(None),
            )
            .all()
        )

        buckets = [
            HistogramBucket(
                bucket_start=i,
                bucket_end=i + 1,
                count=sum(1 for r in reviews if i <= r.rating < (i + 1 if i < 9 else 11)),
            )
            for i in range(10)
        ]

        if not reviews:
            return AlbumStatsResponse(average_rating=None, review_count=0, histogram=buckets)

        ratings = [r.rating for r in reviews]
        avg = round(sum(ratings) / len(ratings), 2)
        return AlbumStatsResponse(average_rating=avg, review_count=len(ratings), histogram=buckets)

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

        was_draft = review.is_draft

        if data.rating is not None:
            review.rating = data.rating
        if data.comment is not None:
            review.comment = data.comment
        if data.is_draft is not None:
            review.is_draft = data.is_draft

        if not review.is_draft and review.rating is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating is required to submit a review",
            )

        self.db.commit()
        self.db.refresh(review)

        if was_draft and not review.is_draft:
            self._notify_co_reviewers(review.album_id, user_id)

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
