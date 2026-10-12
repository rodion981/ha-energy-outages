"""Upcoming/current outage windows using only published schedule coverage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from .const import SCHEDULE_TIME_ZONE
from .coordinator import schedule_day_status


@dataclass(frozen=True, kw_only=True)
class OutageWindow:
    """A known start and an optional, explicitly published end."""

    start: datetime
    end: datetime | None
    start_known: bool = True

    @property
    def duration_minutes(self) -> float | None:
        if self.end is None or not self.start_known:
            return None
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True, kw_only=True)
class ScheduleForecast:
    """Separate the next start from the current-or-next restoration window."""

    next_outage: OutageWindow | None = None
    selected: OutageWindow | None = None
    context: str = "none"
    coverage_end: datetime | None = None


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time(), SCHEDULE_TIME_ZONE).astimezone(UTC)


def _dated_periods(hours: list[int], day: date) -> list[tuple[datetime, datetime]]:
    """Apply wall-clock codes on actual UTC half hours, including 23/25-hour days."""
    cursor = _utc_midnight(day)
    end = _utc_midnight(day + timedelta(days=1))
    start: datetime | None = None
    periods = []
    while cursor < end:
        local = cursor.astimezone(SCHEDULE_TIME_ZONE)
        code = hours[local.hour]
        off = code == 1 or code == (2 if local.minute < 30 else 3)
        if off and start is None:
            start = cursor
        elif not off and start is not None:
            periods.append((start, cursor))
            start = None
        cursor += timedelta(minutes=30)
    if start is not None:
        periods.append((start, end))
    return periods


def schedule_forecast(data: dict[str, Any], now: datetime) -> ScheduleForecast:
    """Never infer restoration across an unpublished day or beyond the horizon."""
    now = now.astimezone(UTC)
    if schedule_day_status(data, "today", now) != "published":
        return ScheduleForecast()
    today = now.astimezone(SCHEDULE_TIME_ZONE).date()
    coverage_start = _utc_midnight(today)
    periods = _dated_periods(data["today"], today)
    coverage_end = _utc_midnight(today + timedelta(days=1))
    if schedule_day_status(data, "tomorrow", now) == "published":
        periods += _dated_periods(data["tomorrow"], today + timedelta(days=1))
        coverage_end = _utc_midnight(today + timedelta(days=2))
    merged: list[tuple[datetime, datetime]] = []
    for start, end in periods:
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    current = None
    next_outage = None
    for start, end in merged:
        window = OutageWindow(
            start=start,
            end=None if end == coverage_end else end,
            start_known=start != coverage_start,
        )
        if start <= now < end:
            current = window
        elif start > now and next_outage is None:
            next_outage = window
    return ScheduleForecast(
        next_outage=next_outage,
        selected=current or next_outage,
        context="current" if current else "next" if next_outage else "none",
        coverage_end=coverage_end,
    )
