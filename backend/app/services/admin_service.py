"""Site-wide operational metrics for the admin panel.

Deliberately narrow. Content statistics — top-rated albums, most-nominated
artists, platform totals — already exist in ``ExploreService.get_site_stats``
and are served publicly at ``GET /explore/stats``; the admin page calls that
rather than growing a second copy here. What this service adds is the part
that endpoint has no notion of: growth and recency.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Album, Group, Review, User
from app.schemas.admin import AdminMetricsResponse, MetricPair, TimeSeriesPoint
from app.services.link_report_service import LinkReportService


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def get_admin_metrics(self, days: int = 30) -> AdminMetricsResponse:
        """Counts, growth, and two day-series for the dashboard.

        Caveat worth knowing: users.created_at, groups.created_at, albums.added_at
        and reviews.reviewed_at are all nullable (server_default only). Rows with a
        NULL timestamp are counted in `total` but are invisible to `recent` and to
        the day series, since NULL fails the cutoff comparison.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        users = self._pair(User.created_at, cutoff, User.id, User.is_bot.is_(False))
        groups = self._pair(Group.created_at, cutoff, Group.id)
        albums = self._pair(Album.added_at, cutoff, Album.id)
        reviews = self._pair(Review.reviewed_at, cutoff, Review.id, Review.is_draft.is_(False))

        return AdminMetricsResponse(
            users=users,
            groups=groups,
            albums=albums,
            reviews=reviews,
            signups_by_day=self._series(User.created_at, cutoff, User.is_bot.is_(False)),
            reviews_by_day=self._series(Review.reviewed_at, cutoff, Review.is_draft.is_(False)),
            open_link_reports=LinkReportService(self.db).count_open(),
            window_days=days,
        )

    def _pair(self, timestamp_col, cutoff: datetime, id_col, *filters) -> MetricPair:
        """Total and in-window count for one table, in a single round trip.

        The filtered aggregate is what lets both numbers come back together —
        two separate COUNT queries would double the trips to Neon for no gain.
        """
        row = self.db.execute(
            select(
                func.count(id_col).label("total"),
                func.count(id_col).filter(timestamp_col >= cutoff).label("recent"),
            ).where(*filters)
        ).one()
        return MetricPair(total=row.total or 0, recent=row.recent or 0)

    def _series(self, timestamp_col, cutoff: datetime, *filters) -> list[TimeSeriesPoint]:
        """Per-day counts since the cutoff, oldest first.

        Bounded by the cutoff rather than scanning all history — these are the only
        queries here predicated on an unindexed column, and the window is what keeps
        that cheap. Days with no rows are simply absent; the client renders gaps.
        """
        day = func.date_trunc("day", timestamp_col).label("day")
        rows = self.db.execute(
            select(day, func.count().label("count"))
            .where(timestamp_col >= cutoff, *filters)
            .group_by(day)
            .order_by(day)
        ).all()
        return [TimeSeriesPoint(day=r.day.date(), count=r.count) for r in rows]
