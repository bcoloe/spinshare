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
