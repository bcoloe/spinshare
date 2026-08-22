"""Tests for AdminService site metrics."""

from datetime import datetime, timedelta, timezone

from app.models import Album, Review, User


def _aged(db_session, obj, column: str, days_ago: int):
    """Backdate a timestamp column so window boundaries can be exercised."""
    setattr(obj, column, datetime.now(timezone.utc) - timedelta(days=days_ago))
    db_session.commit()
    return obj


class TestAdminMetrics:
    def test_empty_database_returns_zeros(self, admin_service):
        metrics = admin_service.get_admin_metrics()

        assert metrics.users.total == 0
        assert metrics.users.recent == 0
        assert metrics.albums.total == 0
        assert metrics.reviews.total == 0
        assert metrics.signups_by_day == []
        assert metrics.reviews_by_day == []
        assert metrics.open_link_reports == 0
        assert metrics.window_days == 30

    def test_counts_exclude_bot_users(self, db_session, admin_service, user_factory):
        user_factory(email="human@test.com", username="human")
        bot = user_factory(email="bot@test.com", username="bot")
        bot.is_bot = True
        db_session.commit()

        metrics = admin_service.get_admin_metrics()

        assert metrics.users.total == 1
        assert metrics.users.recent == 1

    def test_counts_exclude_draft_reviews(
        self, db_session, admin_service, sample_user, sample_album
    ):
        # One review per (user, album), so the draft needs its own album.
        drafted = Album(spotify_album_id="spotify_draft", title="Amnesiac", artist="Radiohead")
        db_session.add(drafted)
        db_session.commit()

        db_session.add_all([
            Review(album_id=sample_album.id, user_id=sample_user.id, rating=8, is_draft=False),
            Review(album_id=drafted.id, user_id=sample_user.id, rating=5, is_draft=True),
        ])
        db_session.commit()

        metrics = admin_service.get_admin_metrics()

        assert metrics.reviews.total == 1

    def test_recent_window_respects_days_arg(
        self, db_session, admin_service, user_factory
    ):
        recent = user_factory(email="r@test.com", username="recentuser")
        old = user_factory(email="o@test.com", username="olduser")
        _aged(db_session, recent, "created_at", 3)
        _aged(db_session, old, "created_at", 100)

        metrics = admin_service.get_admin_metrics(days=30)

        assert metrics.users.total == 2  # totals ignore the window
        assert metrics.users.recent == 1

        wider = admin_service.get_admin_metrics(days=365)
        assert wider.users.recent == 2
        assert wider.window_days == 365

    def test_series_covers_requested_window_only(
        self, db_session, admin_service, user_factory
    ):
        inside = user_factory(email="i@test.com", username="insideuser")
        outside = user_factory(email="x@test.com", username="outsideuser")
        _aged(db_session, inside, "created_at", 2)
        _aged(db_session, outside, "created_at", 90)

        metrics = admin_service.get_admin_metrics(days=30)

        assert len(metrics.signups_by_day) == 1
        assert metrics.signups_by_day[0].count == 1

    def test_series_is_ordered_oldest_first(
        self, db_session, admin_service, user_factory
    ):
        for i, days_ago in enumerate((1, 5, 3)):
            u = user_factory(email=f"s{i}@test.com", username=f"seriesuser{i}")
            _aged(db_session, u, "created_at", days_ago)

        days = [p.day for p in admin_service.get_admin_metrics().signups_by_day]

        assert days == sorted(days)

    def test_series_groups_same_day_signups(
        self, db_session, admin_service, user_factory
    ):
        for i in range(3):
            u = user_factory(email=f"g{i}@test.com", username=f"groupeduser{i}")
            _aged(db_session, u, "created_at", 4)

        series = admin_service.get_admin_metrics().signups_by_day

        assert len(series) == 1
        assert series[0].count == 3

    def test_album_and_group_counts(
        self, db_session, admin_service, sample_album, group_factory
    ):
        db_session.add(Album(spotify_album_id="spotify_second", title="Kid A", artist="Radiohead"))
        db_session.commit()
        group_factory(name="a group")

        metrics = admin_service.get_admin_metrics()

        assert metrics.albums.total == 2
        assert metrics.groups.total >= 1

    def test_open_link_report_count_included(
        self, admin_service, link_report_service, sample_album, sample_user
    ):
        from app.schemas.link_report import LinkReportCreate, ReportableLink, ReportReason

        link_report_service.create(
            sample_album.id,
            sample_user,
            LinkReportCreate(
                link_field=ReportableLink.Spotify, reason_code=ReportReason.Bad
            ),
        )

        assert admin_service.get_admin_metrics().open_link_reports == 1

    def test_rows_with_null_timestamps_count_in_total_but_not_recent(
        self, db_session, admin_service
    ):
        """Documented caveat: these timestamp columns are nullable."""
        user = User(email="null@test.com", username="nulluser", password_hash="x")
        db_session.add(user)
        db_session.commit()
        user.created_at = None
        db_session.commit()

        metrics = admin_service.get_admin_metrics()

        assert metrics.users.total == 1
        assert metrics.users.recent == 0
