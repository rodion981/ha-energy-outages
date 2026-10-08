"""Data coordinator and schedule helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AlertsEnergyApi, AlertsEnergyApiError
from .const import (
    CONF_OPERATOR,
    DEFAULT_OPERATOR,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
    SCHEDULE_TIME_ZONE,
)

_LOGGER = logging.getLogger(__name__)

type OutagePeriod = tuple[int, int]


def outage_periods(hours: list[int]) -> list[OutagePeriod]:
    """Convert 24 hourly codes to half-hour boundaries in the range 0..48."""
    if len(hours) != 24 or any(
        type(value) is not int or value not in range(4) for value in hours
    ):
        raise ValueError("Expected 24 integer outage codes in the range 0..3")
    halves: list[bool] = []
    for value in hours:
        halves.extend((value in (1, 2), value in (1, 3)))

    periods: list[OutagePeriod] = []
    start: int | None = None
    for index, is_outage in enumerate(halves):
        if is_outage and start is None:
            start = index
        elif not is_outage and start is not None:
            periods.append((start, index))
            start = None
    if start is not None:
        periods.append((start, 48))
    return periods


def format_boundary(boundary: int) -> str:
    """Format a half-hour boundary as HH:MM."""
    return f"{boundary // 2:02d}:{(boundary % 2) * 30:02d}"


def format_periods(
    periods: list[OutagePeriod], no_outages: str = "Без відключень"
) -> str:
    """Format all outage periods for a sensor state."""
    if not periods:
        return no_outages
    parts = [
        f"{format_boundary(start)}–{format_boundary(end)}" for start, end in periods
    ]
    result = "; ".join(parts)
    if len(result) <= 255:
        return result
    for count in range(len(parts) - 1, 0, -1):
        result = "; ".join(parts[:count]) + f"; … (+{len(parts) - count})"
        if len(result) <= 255:
            return result
    return "…"


def schedule_day_status(data: dict[str, Any] | None, day: str) -> str:
    """Distinguish published schedules from missing, stale or invalid data."""
    if not data or not data.get("schedule_found", True):
        return "not_found"
    hours = data.get(day)
    if hours is None or hours == []:
        return "unpublished"
    if (
        not isinstance(hours, list)
        or len(hours) != 24
        or any(type(value) is not int or value not in range(4) for value in hours)
    ):
        return "invalid"
    today = datetime.now(SCHEDULE_TIME_ZONE).date()
    expected = today + timedelta(days=day == "tomorrow")
    if data.get(f"{day}Date") != expected.isoformat():
        return "stale"
    if data.get(f"{day}Status") != "ScheduleApplies":
        return "unpublished"
    return "published"


class AlertsEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Alerts Energy and share the selected schedule with entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AlertsEnergyApi,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self._api = api
        self._operator = entry.data.get(CONF_OPERATOR, DEFAULT_OPERATOR)
        self._queue = entry.data["queue"]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._api.async_get_schedule(self._operator, self._queue)
        except AlertsEnergyApiError as err:
            raise UpdateFailed(str(err)) from err
