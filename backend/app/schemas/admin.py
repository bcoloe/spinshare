"""Schemas for the admin panel's site metrics."""

from datetime import date

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
