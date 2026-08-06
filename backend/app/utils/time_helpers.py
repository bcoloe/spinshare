"""Timezone-aware date helpers shared by the selection and dealer workflows."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func

DEFAULT_TZ = "America/New_York"


def utc_today_range() -> tuple[datetime, datetime]:
    """Return [today_start, tomorrow_start) in UTC for date-boundary queries."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def group_today(tz_name: str) -> date:
    """Return the current calendar date in the given IANA timezone."""
    return datetime.now(tz=ZoneInfo(tz_name)).date()


def date_in_tz(col, tz_name: str):
    """SQLAlchemy expression: extract the calendar date of a UTC timestamp in a given timezone."""
    return func.date(func.timezone(tz_name, col))


def week_start_for(day: date) -> date:
    """Return the Monday on or before ``day`` (ISO week start)."""
    return day - timedelta(days=day.weekday())


def completed_week_bounds(tz_name: str) -> tuple[date, date]:
    """Return the most recently *finished* Mon–Sun week in the given timezone.

    Returns ``(week_start, week_end_exclusive)`` where ``week_end_exclusive`` is
    the Monday that begins the current (in-progress) week and ``week_start`` is
    the Monday seven days earlier. Used by the weekly recap generator to decide
    which week to snapshot once it has fully elapsed.
    """
    current_week_start = week_start_for(group_today(tz_name))
    return current_week_start - timedelta(days=7), current_week_start


def week_bounds_for(week_start: date, tz_name: str) -> tuple[datetime, datetime]:
    """Return tz-aware UTC datetime bounds for the week beginning ``week_start``.

    ``week_start`` is interpreted as midnight in ``tz_name``; the returned
    half-open range ``[start, end)`` spans seven days and is expressed in UTC so
    it can filter tz-aware UTC timestamp columns (added_at, reviewed_at,
    selected_date, guess created_at) directly.
    """
    tz = ZoneInfo(tz_name)
    start_local = datetime(week_start.year, week_start.month, week_start.day, tzinfo=tz)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def most_recent_scheduled_date(today: date, selection_days: list[int]) -> date | None:
    """Return the most recent calendar date (≤ today) that falls on a scheduled draw weekday.

    Looks back up to 7 days. Returns None if selection_days is empty.
    Used so non-draw days show the previous draw's albums rather than an empty state.
    """
    if not selection_days:
        return None
    today_weekday = today.isoweekday() - 1  # isoweekday: 1=Mon…7=Sun → 0=Mon…6=Sun
    for days_back in range(7):
        candidate_weekday = (today_weekday - days_back) % 7
        if candidate_weekday in selection_days:
            return today - timedelta(days=days_back)
    return None
