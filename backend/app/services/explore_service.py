"""Explore service: platform-wide album/group browsing and site statistics."""

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.utils.cache import (
    EXPLORE_ALBUMS_TTL,
    SITE_STATS_TTL,
    _key,
    cache,
)

from app.models.album import Album
from app.models.group import Group
from app.models.group_album import GroupAlbum
from app.models.review import Review
from app.schemas.explore import (
    ArtistNominationItem,
    ExploreAlbumItem,
    ExploreAlbumsPage,
    ExploreGroupItem,
    ExploreGroupsPage,
    SiteStatsResponse,
)

_PAGE_SIZE = 20
_BAYESIAN_MIN_VOTES = 3  # smoothing threshold for weighted score


def _build_album_subqueries(db: Session):
    """Return (nomination_subq, review_stats_subq, global_avg).

    nomination_subq: album_id → nomination_count (distinct GroupAlbum rows)
    review_stats_subq: album_id → review_count, avg_rating (non-draft only)
    global_avg: float — mean rating across all non-draft reviews
    """
    nomination_subq = (
        db.query(
            GroupAlbum.album_id,
            func.count(GroupAlbum.id).label("nomination_count"),
        )
        .group_by(GroupAlbum.album_id)
        .subquery()
    )

    review_stats_subq = (
        db.query(
            Review.album_id,
            func.count(Review.id).label("review_count"),
            func.avg(Review.rating).label("avg_rating"),
        )
        .filter(Review.is_draft == False)  # noqa: E712
        .group_by(Review.album_id)
        .subquery()
    )

    global_avg = (
        db.query(func.avg(Review.rating))
        .filter(Review.is_draft == False)  # noqa: E712
        .scalar()
        or 5.0
    )

    return nomination_subq, review_stats_subq, float(global_avg)


def _bayesian_score_expr(review_stats_subq, global_avg: float):
    """SQLAlchemy expression for Bayesian-weighted score.

    score = (v * R + m * C) / (v + m)
    where v=review_count, R=avg_rating, C=global_avg, m=_BAYESIAN_MIN_VOTES
    """
    m = _BAYESIAN_MIN_VOTES
    v = func.coalesce(review_stats_subq.c.review_count, 0)
    R = func.coalesce(review_stats_subq.c.avg_rating, global_avg)
    return (v * R + m * global_avg) / (v + m)


def _row_to_album_item(row, nomination_count: int, review_count: int, avg_rating, weighted_score) -> ExploreAlbumItem:
    album: Album = row
    return ExploreAlbumItem(
        id=album.id,
        spotify_album_id=album.spotify_album_id,
        title=album.title,
        artist=album.artist,
        artist_url=album.artist_url,
        cover_url=album.cover_url,
        release_date=album.release_date,
        avg_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
        review_count=int(review_count),
        nomination_count=int(nomination_count),
        weighted_score=round(float(weighted_score), 4) if weighted_score is not None else None,
    )


class ExploreService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== ALBUMS ====================

    def get_explore_albums(
        self,
        offset: int = 0,
        limit: int = _PAGE_SIZE,
        min_reviews: int | None = None,
        sort_by: str = "top_rated",
        q: str | None = None,
    ) -> ExploreAlbumsPage:
        """Return a paginated page of albums with review/nomination aggregates.

        sort_by options:
            top_rated      — Bayesian weighted score DESC
            bottom_rated   — Bayesian weighted score ASC
            most_reviewed  — review_count DESC
            most_nominated — nomination_count DESC
            recent         — added_at DESC

        Albums with no nominations are excluded (inner join via nomination_subq).
        q filters by case-insensitive partial match on artist or title.
        """
        ck = _key("explore", "albums", sort_by, min_reviews or 0, offset, limit, q or "")
        cached = cache.get(ck)
        if cached is not None:
            return cached

        nomination_subq, review_stats_subq, global_avg = _build_album_subqueries(self.db)
        bayesian_expr = _bayesian_score_expr(review_stats_subq, global_avg)

        nom_count_col = func.coalesce(nomination_subq.c.nomination_count, 0).label("nomination_count")
        rev_count_col = func.coalesce(review_stats_subq.c.review_count, 0).label("review_count")
        avg_rating_col = review_stats_subq.c.avg_rating.label("avg_rating")
        score_col = bayesian_expr.label("weighted_score")

        db_q = (
            self.db.query(Album, nom_count_col, rev_count_col, avg_rating_col, score_col)
            .join(nomination_subq, Album.id == nomination_subq.c.album_id)
            .outerjoin(review_stats_subq, Album.id == review_stats_subq.c.album_id)
        )

        if q:
            term = f"%{q.lower()}%"
            db_q = db_q.filter(
                Album.title.ilike(term) | Album.artist.ilike(term)
            )

        if min_reviews is not None:
            db_q = db_q.filter(func.coalesce(review_stats_subq.c.review_count, 0) >= min_reviews)

        order_map = {
            "top_rated": score_col.desc(),
            "bottom_rated": score_col.asc(),
            "most_reviewed": rev_count_col.desc(),
            "most_nominated": nom_count_col.desc(),
            "recent": Album.added_at.desc(),
        }
        db_q = db_q.order_by(order_map.get(sort_by, score_col.desc()))

        rows = db_q.offset(offset).limit(limit + 1).all()

        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items = [
            _row_to_album_item(
                row[0],
                nomination_count=row[1],
                review_count=row[2],
                avg_rating=row[3],
                weighted_score=row[4],
            )
            for row in page_rows
        ]

        result = ExploreAlbumsPage(
            items=items,
            next_offset=offset + limit if has_more else None,
        )
        cache.set(ck, result, EXPLORE_ALBUMS_TTL)
        return result

    # ==================== GROUPS ====================

    def get_explore_groups(
        self,
        offset: int = 0,
        limit: int = _PAGE_SIZE,
        q: str | None = None,
        group_type: str = "all",
    ) -> ExploreGroupsPage:
        """Return a paginated page of public groups ordered alphabetically.

        q filters by case-insensitive partial name match.
        group_type: 'all' | 'human' | 'bot'
            bot   — is_global=True
            human — is_global=False
        """
        db_q = (
            self.db.query(Group)
            .options(selectinload(Group.members))
            .filter(Group.is_public == True)  # noqa: E712
            .order_by(func.lower(Group.name))
        )

        if q:
            db_q = db_q.filter(Group.name.ilike(f"%{q}%"))

        if group_type == "bot":
            db_q = db_q.filter(Group.is_global == True)  # noqa: E712
        elif group_type == "human":
            db_q = db_q.filter(Group.is_global == False)  # noqa: E712

        rows = db_q.offset(offset).limit(limit + 1).all()

        has_more = len(rows) > limit
        page_groups = rows[:limit]

        items = [
            ExploreGroupItem(
                id=g.id,
                name=g.name,
                is_public=g.is_public,
                is_global=g.is_global,
                member_count=len(g.members),
                created_at=g.created_at,
            )
            for g in page_groups
        ]

        return ExploreGroupsPage(
            items=items,
            next_offset=offset + limit if has_more else None,
        )

    # ==================== STATS ====================

    def get_site_stats(self) -> SiteStatsResponse:
        """Compute and return platform-wide statistics.

        Totals:
            total_albums_nominated — distinct album_ids ever nominated in any group
            total_reviews          — non-draft reviews recorded
            total_active_groups    — groups with at least one album nominated
            total_active_members   — users belonging to at least one group

        Ranked lists (top 10 each):
            top_rated_albums       — highest Bayesian weighted score, min 3 reviews
            bottom_rated_albums    — lowest Bayesian weighted score, min 3 reviews
            most_nominated_artists — artists by sum of GroupAlbum rows
            most_nominated_albums  — albums by count of GroupAlbum rows
        """
        ck = _key("explore", "site_stats")
        cached = cache.get(ck)
        if cached is not None:
            return cached

        # --- Totals ---
        total_albums_nominated = (
            self.db.query(func.count(func.distinct(GroupAlbum.album_id))).scalar() or 0
        )
        total_reviews = (
            self.db.query(func.count(Review.id))
            .filter(Review.is_draft == False)  # noqa: E712
            .scalar()
            or 0
        )
        total_active_groups = (
            self.db.query(func.count(func.distinct(GroupAlbum.group_id))).scalar() or 0
        )
        from app.models.group import group_members
        total_active_members = (
            self.db.query(func.count(func.distinct(group_members.c.user_id))).scalar() or 0
        )

        # --- Shared subqueries for ranked album lists ---
        nomination_subq, review_stats_subq, global_avg = _build_album_subqueries(self.db)
        bayesian_expr = _bayesian_score_expr(review_stats_subq, global_avg)

        nom_count_col = func.coalesce(nomination_subq.c.nomination_count, 0).label("nomination_count")
        rev_count_col = func.coalesce(review_stats_subq.c.review_count, 0).label("review_count")
        avg_rating_col = review_stats_subq.c.avg_rating.label("avg_rating")
        score_col = bayesian_expr.label("weighted_score")

        base_q = (
            self.db.query(Album, nom_count_col, rev_count_col, avg_rating_col, score_col)
            .join(nomination_subq, Album.id == nomination_subq.c.album_id)
            .outerjoin(review_stats_subq, Album.id == review_stats_subq.c.album_id)
            .filter(func.coalesce(review_stats_subq.c.review_count, 0) >= _BAYESIAN_MIN_VOTES)
        )

        def _to_items(rows) -> list[ExploreAlbumItem]:
            return [
                _row_to_album_item(r[0], nomination_count=r[1], review_count=r[2], avg_rating=r[3], weighted_score=r[4])
                for r in rows
            ]

        top_rated_rows = base_q.order_by(score_col.desc()).limit(10).all()
        bottom_rated_rows = base_q.order_by(score_col.asc()).limit(10).all()

        # --- Most nominated albums (any review count) ---
        most_nominated_rows = (
            self.db.query(Album, nom_count_col, rev_count_col, avg_rating_col, score_col)
            .join(nomination_subq, Album.id == nomination_subq.c.album_id)
            .outerjoin(review_stats_subq, Album.id == review_stats_subq.c.album_id)
            .order_by(nom_count_col.desc())
            .limit(10)
            .all()
        )

        # --- Most nominated artists ---
        artist_rows = (
            self.db.query(
                Album.artist,
                Album.artist_url,
                func.count(GroupAlbum.id).label("nomination_count"),
                func.count(func.distinct(GroupAlbum.album_id)).label("unique_albums"),
            )
            .join(GroupAlbum, Album.id == GroupAlbum.album_id)
            .group_by(Album.artist, Album.artist_url)
            .order_by(func.count(GroupAlbum.id).desc())
            .limit(10)
            .all()
        )
        most_nominated_artists = [
            ArtistNominationItem(
                artist=row.artist,
                artist_url=row.artist_url,
                nomination_count=row.nomination_count,
                unique_albums=row.unique_albums,
            )
            for row in artist_rows
        ]

        result = SiteStatsResponse(
            total_albums_nominated=total_albums_nominated,
            total_reviews=total_reviews,
            total_active_groups=total_active_groups,
            total_active_members=total_active_members,
            top_rated_albums=_to_items(top_rated_rows),
            bottom_rated_albums=_to_items(bottom_rated_rows),
            most_nominated_artists=most_nominated_artists,
            most_nominated_albums=_to_items(most_nominated_rows),
        )
        cache.set(ck, result, SITE_STATS_TTL)
        return result
