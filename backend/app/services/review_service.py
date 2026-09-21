"""Review service."""

import statistics

from app.models import Album, AlbumDeal, Group, GroupAlbum, Review, User, group_members
from app.schemas.album import AlbumReviewItem, AlbumStatsResponse, HistogramBucket, ReviewCreate, ReviewUpdate
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService
from app.services.participation_service import ParticipationService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Hard caps on the unpaginated review listings. These endpoints return a plain
# list (no envelope), so they cannot grow an offset/limit contract without
# changing their response shape; until they do, the cap bounds the worst case
# instead of letting a large group stream its entire review history every load.
_MAX_ALBUM_REVIEWS = 1000
_MAX_GROUP_REVIEWS = 2000


class ReviewService:
    """Service layer for Review operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_review(
        self, album_id: int, user_id: int, data: ReviewCreate, group_id: int | None = None
    ) -> Review:
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
        # Refresh the cached averages BEFORE the notification / credit side effects.
        # Those touch other services and other tables; if one of them raises, the
        # request fails but the review is already committed, and group_albums would
        # keep a stale avg_rating / review_count with nothing left to recompute it.
        # The averages are derived state and must land first.
        self._refresh_group_album_avgs(album_id)
        if not data.is_draft:
            self._notify_co_reviewers(album_id, user_id)
            ParticipationService(self.db).award_review_credit(user_id, review)
        review.is_first_review = (
            not data.is_draft
            and group_id is not None
            and self._is_first_group_review(album_id, group_id, exclude_review_id=review.id)
        )
        return review

    def _is_first_group_review(
        self, album_id: int, group_id: int, *, exclude_review_id: int | None = None
    ) -> bool:
        """Check whether no group member has a published review of this album yet."""
        member_ids = list(
            self.db.scalars(
                select(group_members.c.user_id).where(group_members.c.group_id == group_id)
            ).all()
        )
        if not member_ids:
            return False
        stmt = select(Review.id).where(
            Review.album_id == album_id,
            Review.user_id.in_(member_ids),
            Review.is_draft == False,  # noqa: E712
        )
        if exclude_review_id is not None:
            stmt = stmt.where(Review.id != exclude_review_id)
        existing = self.db.scalar(stmt.limit(1))
        return existing is None

    def _refresh_group_album_avgs(self, album_id: int) -> None:
        """Recompute and cache avg_rating / review_count on all group_albums rows for this album.

        Only published, rated reviews from current group members are counted, matching
        the member-scoped average shown in the review history table.
        """
        rows = list(
            self.db.scalars(select(GroupAlbum).where(GroupAlbum.album_id == album_id)).all()
        )
        if not rows:
            return

        # One membership-joined fetch covering every affected group, rather than
        # a member lookup plus a ratings fetch per GroupAlbum row. Rows are keyed
        # by (group, album, added_by), so a co-nominated album repeated the same
        # two queries verbatim for every nominator in the same group, on every
        # review create/update/delete.
        #
        # Deliberately returns the ratings rather than SUM/AVG: the mean is
        # rounded to two decimals, and rating means land on an exact .xx5 tie
        # often enough (~5% of the time on a one-decimal rating scale) that the
        # difference between Postgres float8 accumulation and Python's — a few
        # ulps — flips the cached value by 0.01 on roughly 1% of albums. Every
        # other average in the app is computed this way, so the aggregate would
        # disagree with them. One row per (group, reviewing member) is a handful
        # of floats; the cost here was always the round trips, not the volume.
        group_ids = {ga.group_id for ga in rows}
        ratings_by_group: dict[int, list[float]] = {}
        for group_id, rating in self.db.execute(
            select(group_members.c.group_id, Review.rating)
            .join(Review, Review.user_id == group_members.c.user_id)
            .where(
                group_members.c.group_id.in_(group_ids),
                Review.album_id == album_id,
                Review.is_draft == False,  # noqa: E712
                Review.rating.isnot(None),
            )
            # Deterministic accumulation order, so the same ratings always round
            # to the same cached average.
            .order_by(group_members.c.group_id, Review.id)
        ).all():
            ratings_by_group.setdefault(group_id, []).append(rating)

        for ga in rows:
            ratings = ratings_by_group.get(ga.group_id, [])
            ga.avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
            ga.review_count = len(ratings)
        self.db.commit()

    def _notify_co_reviewers(self, album_id: int, reviewer_id: int) -> None:
        """Notify group members who already reviewed this album that a new review was posted.

        Only fires for non-global groups where the reviewer is also a member.
        Each co-reviewer receives at most one notification, scoped to the first
        group they share with the reviewer, so they can navigate directly to the review.
        """
        album = self.db.get(Album, album_id)
        reviewer = self.db.get(User, reviewer_id)
        if not album or not reviewer:
            return

        groups_with_album = list(
            self.db.scalars(
                select(GroupAlbum)
                .join(Group, GroupAlbum.group_id == Group.id)
                .where(GroupAlbum.album_id == album_id, Group.is_global == False)  # noqa: E712
            ).all()
        )
        if not groups_with_album:
            return

        # The membership and co-reviewer lookups used to run once per GroupAlbum
        # row; both collapse into a single IN query covering every candidate
        # group. Intersecting in Python is equivalent to the per-group
        # `Review.user_id.in_(member_ids)` filter.
        group_ids = {ga.group_id for ga in groups_with_album}
        members_by_group: dict[int, set[int]] = {}
        for group_id, user_id in self.db.execute(
            select(group_members.c.group_id, group_members.c.user_id).where(
                group_members.c.group_id.in_(group_ids)
            )
        ).all():
            members_by_group.setdefault(group_id, set()).add(user_id)

        co_reviewer_ids = set(
            self.db.scalars(
                select(Review.user_id).where(
                    Review.album_id == album_id,
                    Review.user_id != reviewer_id,
                    Review.is_draft == False,  # noqa: E712
                )
            ).all()
        )
        if not co_reviewer_ids:
            return

        # Each recipient is still scoped to the first group they share with the
        # reviewer; dicts preserve insertion order, so the fan-out order matches
        # the per-notification loop this replaced.
        recipients_by_group: dict[int, list[int]] = {}
        already_notified: set[int] = set()
        for ga in groups_with_album:
            member_ids = members_by_group.get(ga.group_id, set())
            if reviewer_id not in member_ids:
                continue
            for uid in sorted(co_reviewer_ids & member_ids):
                if uid not in already_notified:
                    recipients_by_group.setdefault(ga.group_id, []).append(uid)
                    already_notified.add(uid)

        ns = NotificationService(self.db)
        message = f"{reviewer.username} also reviewed {album.title}"
        for group_id, user_ids in recipients_by_group.items():
            ns.create_many(
                user_ids=user_ids,
                type=NotificationType.member_reviewed_album,
                message=message,
                group_id=group_id,
                album_id=album_id,
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

        Capped at ``_MAX_ALBUM_REVIEWS`` (oldest first) so a heavily reviewed
        album cannot return an unbounded page.
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
            .order_by(Review.id)
            .limit(_MAX_ALBUM_REVIEWS)
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
        # Just the ratings, not whole Review rows: the response is eleven
        # numbers, and hydrating a mapped object per review to read one float
        # off it was the bulk of the work here.
        #
        # The histogram and the moments stay in Python rather than becoming
        # conditional SQL counts plus AVG/STDDEV_POP. Both statistics are
        # rounded to two decimals, and rating means land on an exact .xx5 tie
        # often enough that Postgres float8 accumulation and Python's disagree
        # by 0.01 on ~1% of albums (~0.2% for the spread) — a visible drift, and
        # one that would put this endpoint out of step with every other average
        # in the app. This was never a round-trip problem: it is one query
        # either way.
        ratings = list(
            self.db.scalars(
                select(Review.rating)
                .where(
                    Review.album_id == album_id,
                    Review.is_draft == False,  # noqa: E712
                    Review.rating.isnot(None),
                )
                .order_by(Review.id)
            ).all()
        )

        # Single pass, rather than one scan of the list per bucket.
        counts = [0] * 10
        for rating in ratings:
            counts[min(int(rating), 9)] += 1
        buckets = [
            HistogramBucket(bucket_start=i, bucket_end=i + 1, count=counts[i]) for i in range(10)
        ]

        if not ratings:
            return AlbumStatsResponse(
                average_rating=None, rating_stddev=None, review_count=0, histogram=buckets
            )

        avg = round(sum(ratings) / len(ratings), 2)
        # Population std dev — a spread/contentiousness measure (0.0 for a single rating).
        stddev = round(statistics.pstdev(ratings), 2)
        return AlbumStatsResponse(
            average_rating=avg, rating_stddev=stddev, review_count=len(ratings), histogram=buckets
        )

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

    def get_my_reviews_for_group(self, group_id: int, user_id: int) -> list[Review]:
        """Return the current user's reviews for the group's history albums.

        History albums are the union of shared selections and albums dealt to
        the user (dealer mode).
        """
        album_ids = set(
            self.db.scalars(
                select(GroupAlbum.album_id).where(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.selected_date.isnot(None),
                )
            ).all()
        ) | set(
            self.db.scalars(
                select(AlbumDeal.album_id).where(
                    AlbumDeal.group_id == group_id,
                    AlbumDeal.user_id == user_id,
                    AlbumDeal.revealed_at.isnot(None),
                )
            ).all()
        )
        if not album_ids:
            return []
        return list(
            self.db.scalars(
                select(Review).where(
                    Review.album_id.in_(album_ids),
                    Review.user_id == user_id,
                )
            ).all()
        )

    def get_all_reviews_for_group(self, group_id: int, viewer_id: int) -> list[AlbumReviewItem]:
        """Return all published reviews for all history albums in a group.

        History albums are the union of shared selections and albums dealt to
        any member (dealer mode).

        Applies the same privacy rules as get_reviews_for_album: names are
        shown when reviewer has name_is_public=True, or the viewer is a
        non-global group member.

        Capped at ``_MAX_GROUP_REVIEWS`` (oldest first) so a long-running group
        cannot return an unbounded page.
        """
        show_names_in_group = False
        group = self.db.query(Group).filter(Group.id == group_id).first()
        if group and not group.is_global:
            is_member = self.db.execute(
                select(group_members).where(
                    group_members.c.group_id == group_id,
                    group_members.c.user_id == viewer_id,
                )
            ).first()
            show_names_in_group = is_member is not None

        album_ids = set(
            self.db.scalars(
                select(GroupAlbum.album_id).where(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.selected_date.isnot(None),
                )
            ).all()
        ) | set(
            self.db.scalars(
                select(AlbumDeal.album_id).where(
                    AlbumDeal.group_id == group_id,
                    AlbumDeal.revealed_at.isnot(None),
                )
            ).all()
        )
        if not album_ids:
            return []

        rows = (
            self.db.query(Review, User.username, User.first_name, User.last_name, User.name_is_public)
            .join(User, Review.user_id == User.id)
            .filter(
                Review.album_id.in_(album_ids),
                Review.is_draft == False,  # noqa: E712
            )
            .order_by(Review.id)
            .limit(_MAX_GROUP_REVIEWS)
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

    # ==================== UPDATE ====================

    def update_review(
        self, review_id: int, user_id: int, data: ReviewUpdate, group_id: int | None = None
    ) -> Review:
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

        just_published = was_draft and not review.is_draft

        self.db.commit()
        self.db.refresh(review)

        # Same ordering rule as create_review: land the derived averages first, so a
        # failure in the notification / credit side effects cannot leave an edited
        # rating permanently uncounted in group_albums.
        self._refresh_group_album_avgs(review.album_id)
        if just_published:
            self._notify_co_reviewers(review.album_id, user_id)
            ParticipationService(self.db).award_review_credit(user_id, review)

        review.is_first_review = (
            just_published
            and group_id is not None
            and self._is_first_group_review(review.album_id, group_id, exclude_review_id=review.id)
        )

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
        album_id = review.album_id
        self.db.delete(review)
        self.db.commit()
        self._refresh_group_album_avgs(album_id)
