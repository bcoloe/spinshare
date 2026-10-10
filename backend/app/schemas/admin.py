"""Schemas for the admin panel's site metrics and scheduler status."""

from datetime import date, datetime

from pydantic import BaseModel


class MetricPair(BaseModel):
    """A running total plus how much of it arrived inside the requested window."""

    total: int
    recent: int


class TimeSeriesPoint(BaseModel):
    day: date
    count: int


class AdminMetricsResponse(BaseModel):
    users: MetricPair
    groups: MetricPair
    albums: MetricPair
    reviews: MetricPair
    signups_by_day: list[TimeSeriesPoint]
    reviews_by_day: list[TimeSeriesPoint]
    open_link_reports: int
    window_days: int


class JobOutcome(BaseModel):
    done: int
    rejected: int
    failed: int


class SchedulerRun(BaseModel):
    ran_at: datetime
    selection: JobOutcome
    recap: JobOutcome


class ScheduledGroup(BaseModel):
    group_id: int
    timezone: str
    selected_on: date | None
    next_selection_at: datetime | None
    recapped_week: date | None
    next_recap_at: datetime | None
    retry_at: datetime | None


class SchedulerStatusResponse(BaseModel):
    """What the in-process job scheduler has done and plans to do next.

    ``selected_on`` / ``recapped_week`` reflect only this process's lifetime; they
    are empty until the first tick after a restart catches each group up.
    """

    running: bool
    started_at: datetime | None
    last_tick_at: datetime | None
    last_error: str | None
    selection_hour: int
    recap_hour: int
    schedule_loaded: bool
    recent_runs: list[SchedulerRun]
    groups: list[ScheduledGroup]
