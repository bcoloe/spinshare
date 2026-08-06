"""Tests for weekly-recap timezone/date helpers."""

from datetime import date, datetime, timezone

from app.utils.time_helpers import (
    completed_week_bounds,
    week_bounds_for,
    week_start_for,
)


class TestWeekStartFor:
    def test_monday_returns_itself(self):
        assert week_start_for(date(2026, 7, 27)) == date(2026, 7, 27)

    def test_midweek_snaps_back_to_monday(self):
        assert week_start_for(date(2026, 7, 29)) == date(2026, 7, 27)  # Wed → Mon

    def test_sunday_snaps_back_to_monday(self):
        assert week_start_for(date(2026, 8, 2)) == date(2026, 7, 27)  # Sun → prior Mon


class TestCompletedWeekBounds:
    def test_returns_full_prior_week(self):
        start, end = completed_week_bounds("America/New_York")
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 0  # Monday
        assert (end - start).days == 7

    def test_end_is_current_week_monday(self):
        from app.utils.time_helpers import group_today

        start, end = completed_week_bounds("UTC")
        # The completed week ends where the in-progress (current) week begins.
        assert end == week_start_for(group_today("UTC"))
        assert start < end


class TestWeekBoundsFor:
    def test_edt_offset_converts_local_midnight_to_utc(self):
        # July 27 2026 is during EDT (UTC-4); local midnight = 04:00 UTC.
        start, end = week_bounds_for(date(2026, 7, 27), "America/New_York")
        assert start == datetime(2026, 7, 27, 4, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc)

    def test_span_is_seven_days_and_utc(self):
        start, end = week_bounds_for(date(2026, 7, 27), "UTC")
        assert start == datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
        assert (end - start).days == 7
        assert start.tzinfo is timezone.utc and end.tzinfo is timezone.utc
