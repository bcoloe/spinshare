"""Tests for the shared daily-selection / weekly-recap runners."""

import pytest

from app.models import GroupAlbum, GroupSettings
from app.services import scheduled_jobs
from app.services.group_album_service import GroupAlbumService
from app.services.scheduled_jobs import run_daily_selection, run_weekly_recaps


@pytest.fixture
def two_groups(group_factory, db_session, sample_album, sample_user):
    """Two groups, each with one pending nomination."""
    groups = [group_factory(name="Alpha"), group_factory(name="Bravo")]
    for group in groups:
        db_session.add(GroupAlbum(group_id=group.id, album_id=sample_album.id, added_by=sample_user.id))
    db_session.commit()
    return groups


class TestRunDailySelection:
    def test_draws_every_requested_group(self, db_session, two_groups):
        ids = [g.id for g in two_groups]

        report = run_daily_selection(db_session, ids)

        assert report.done == ids
        selected = db_session.query(GroupAlbum).filter(GroupAlbum.group_id.in_(ids)).all()
        assert all(ga.selected_date is not None for ga in selected)

    def test_an_empty_pool_is_rejected_not_failed(self, db_session, group_factory):
        """A business refusal (409) is final for the day; only real faults are retried."""
        group = group_factory(name="Empty")

        report = run_daily_selection(db_session, [group.id])

        assert list(report.rejected) == [group.id]
        assert report.failed == {}

    def test_n_overrides_the_configured_count(self, db_session, two_groups, monkeypatch):
        seen = []
        original = GroupAlbumService.select_daily_albums
        monkeypatch.setattr(
            GroupAlbumService, "select_daily_albums",
            lambda self, gid, n=1, **kw: seen.append(n) or original(self, gid, n=n, **kw),
        )

        run_daily_selection(db_session, [two_groups[0].id], n=3)

        assert seen == [3]

    def test_a_failing_group_does_not_stop_the_ones_after_it(self, db_session, two_groups, monkeypatch):
        """The failure rolls the shared Session back so the next group can still run."""
        first, second = two_groups
        original = GroupAlbumService.select_daily_albums

        def flaky(self, gid, n=1, **kw):
            if gid == first.id:
                self.db.execute(scheduled_jobs.Group.__table__.select().where(1 == 0))
                raise RuntimeError("deadlock detected")
            return original(self, gid, n=n, **kw)

        monkeypatch.setattr(GroupAlbumService, "select_daily_albums", flaky)

        report = run_daily_selection(db_session, [first.id, second.id])

        assert list(report.failed) == [first.id]
        assert report.done == [second.id]

    def test_unscheduled_day_is_done_without_drawing(self, db_session, two_groups):
        group = two_groups[0]
        settings = db_session.query(GroupSettings).filter_by(group_id=group.id).one()
        settings.selection_days = []
        db_session.commit()

        report = run_daily_selection(db_session, [group.id])

        assert report.done == [group.id]
        ga = db_session.query(GroupAlbum).filter_by(group_id=group.id).one()
        assert ga.selected_date is None


class TestRunWeeklyRecaps:
    def test_ineligible_group_is_done_with_nothing_generated(self, db_session, global_group):
        report = run_weekly_recaps(db_session, [global_group.id])
        assert report.done == [global_group.id]

    def test_explicit_week_for_ineligible_group_is_rejected(self, db_session, global_group):
        from datetime import date

        report = run_weekly_recaps(db_session, [global_group.id], week_start=date(2026, 9, 28))
        assert list(report.rejected) == [global_group.id]
