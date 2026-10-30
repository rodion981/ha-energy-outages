"""Data coordinator and schedule helpers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, current_entry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AlertsEnergyApi, AlertsEnergyApiError
from .const import (
    CONF_OPERATOR,
    CONF_SCAN_INTERVAL,
    DATA_AREAS,
    DEFAULT_OPERATOR,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
    RETRY_INTERVAL_SECONDS,
    SCAN_INTERVAL_SECONDS,
    SCHEDULE_TIME_ZONE,
)
from .schedule import normalize_day

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


def schedule_day_status(
    data: dict[str, Any] | None, day: str, now: datetime | None = None
) -> str:
    """Distinguish published schedules from missing, stale or invalid data."""
    if not data or not data.get("schedule_found", True):
        return "not_found"
    today = (now or dt_util.utcnow()).astimezone(SCHEDULE_TIME_ZONE).date()
    expected = today + timedelta(days=day == "tomorrow")
    emergency = data.get(f"{day}Status") == "EmergencyShutdowns" or any(
        isinstance(values, list)
        and any(type(code) is int and code == 9 for code in values)
        for values in (data.get(day), data.get(f"{day}Possible"))
    )
    if data.get(f"{day}Date") == expected.isoformat() and emergency:
        return "emergency"
    hours = data.get(day)
    if hours is None or hours == []:
        return "unpublished"
    try:
        normalized = normalize_day(data, day)
    except ValueError:
        return "invalid"
    if data.get(f"{day}Date") != expected.isoformat():
        return "stale"
    source_status = data.get(f"{day}Status")
    if source_status == "NoShutdowns":
        return "published" if not any(normalized.planned) else "invalid"
    if source_status != "ScheduleApplies":
        return "unpublished"
    return "published"


def period_attributes(hours: list[int]) -> list[dict[str, str]]:
    """Expose complete machine-readable periods, independently of state length."""
    return [
        {"start": format_boundary(start), "end": format_boundary(end)}
        for start, end in outage_periods(hours)
    ]


class AlertsEnergyAreaCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Own one poller, clock listener and update health per active area."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AlertsEnergyApi,
        area: str,
    ) -> None:
        # HA 2024.6 captures current_entry implicitly. A shared poller must not
        # inherit the first entry's unload callback or stop when it is removed.
        token = current_entry.set(None)
        try:
            super().__init__(
                hass,
                logger=_LOGGER,
                name=f"{DOMAIN} {area}",
                update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
            )
        finally:
            current_entry.reset(token)
        self._api = api
        self.data: list[dict[str, Any]] | None = None
        self.area = area
        self.users = 0
        self._configured_update_interval = timedelta(seconds=SCAN_INTERVAL_SECONDS)
        self._retry_seconds: float = RETRY_INTERVAL_SECONDS
        self.last_successful_update: datetime | None = None
        self._initial_lock = asyncio.Lock()
        self._unsub_clock: Callable[[], None] | None = async_track_utc_time_change(
            hass, self._handle_clock, minute=[0, 30], second=0
        )

    @callback
    def _handle_clock(self, _now: datetime) -> None:
        self.async_update_listeners()

    def _schedule_refresh(self) -> None:
        """Keep the existing disable-polling preference for the shared source."""
        if any(not entry.pref_disable_polling for entry in self.async_contexts()):
            self.update_interval = (
                self._configured_update_interval
                if self.last_update_success
                else max(
                    self._configured_update_interval,
                    timedelta(
                        seconds=max(
                            self._retry_seconds, self._api.retry_delay(self.area)
                        )
                    ),
                )
            )
            super()._schedule_refresh()

    @callback
    def async_update_polling_schedule(self) -> None:
        """Use the shortest interval requested by polling-enabled entries."""
        self._configured_update_interval = timedelta(
            minutes=max(
                MIN_SCAN_INTERVAL_MINUTES,
                min(
                    (
                        entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                        )
                        for entry in self.async_contexts()
                        if not entry.pref_disable_polling
                    ),
                    default=DEFAULT_SCAN_INTERVAL_MINUTES,
                ),
            )
        )
        self.update_interval = self._configured_update_interval
        self._async_unsub_refresh()
        if not self._shutdown_requested:
            self._schedule_refresh()

    async def async_ensure_ready(self) -> None:
        """Coalesce startup and permit a retained response with truthful health."""
        async with self._initial_lock:
            if self.data is None or not self.last_update_success:
                await self.async_refresh()
                if self.data is None:
                    raise ConfigEntryNotReady(
                        str(self.last_exception or "No regional data received")
                    ) from self.last_exception

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            rows = await self._api.async_get_schedules(self.area)
        except AlertsEnergyApiError as err:
            self._retry_seconds = max(RETRY_INTERVAL_SECONDS, err.retry_after)
            if (
                self.data is None
                and (snapshot := self._api.cached_schedule(self.area)) is not None
            ):
                self.data, self.last_successful_update = snapshot
            raise UpdateFailed(str(err)) from err
        snapshot = self._api.cached_schedule(self.area)
        self.last_successful_update = snapshot[1] if snapshot else dt_util.utcnow()
        return rows

    async def async_shutdown(self) -> None:
        if self._unsub_clock is not None:
            self._unsub_clock()
            self._unsub_clock = None
        await super().async_shutdown()


async def async_acquire_area(
    hass: HomeAssistant, api: AlertsEnergyApi, area: str
) -> AlertsEnergyAreaCoordinator:
    """Acquire an area before awaiting setup so concurrent entries share it."""
    areas = hass.data.setdefault(DOMAIN, {}).setdefault(DATA_AREAS, {})
    source = areas.get(area)
    if source is None:
        source = areas[area] = AlertsEnergyAreaCoordinator(hass, api, area)
        await source.async_register_shutdown()
    source.users += 1
    try:
        await source.async_ensure_ready()
    except BaseException:
        await async_release_area(hass, source)
        raise
    return source


async def async_release_area(
    hass: HomeAssistant, source: AlertsEnergyAreaCoordinator
) -> None:
    """Stop and discard the source only after the final entry releases it."""
    source.users -= 1
    if source.users == 0:
        areas = hass.data[DOMAIN][DATA_AREAS]
        if areas.get(source.area) is source:
            areas.pop(source.area)
        await source.async_shutdown()


class AlertsEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Expose one entry's row while its area owns polling and time updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        source: AlertsEnergyAreaCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(hass, logger=_LOGGER, name=DOMAIN)
        self.source = source
        self.area = source.area
        self._operator = entry.data.get(CONF_OPERATOR, DEFAULT_OPERATOR)
        self._queue = entry.data["queue"]
        self._closed = False
        self._unsub_source = source.async_add_listener(
            self._handle_source_update, context=entry
        )
        self._handle_source_update()
        source.async_update_polling_schedule()

    @property
    def last_successful_update(self) -> datetime | None:
        return self.source.last_successful_update

    @property
    def data_is_cached(self) -> bool:
        """Distinguish a retained response from a successful current update."""
        return self.source.data is not None and not self.last_update_success

    @property
    def data_status(self) -> str:
        """Explain unavailable data without treating transport errors as outages."""
        if not self.last_update_success:
            cause = self.last_exception.__cause__ if self.last_exception else None
            if isinstance(cause, AlertsEnergyApiError):
                return cause.reason
            return "connection_error"
        now = dt_util.utcnow()
        if (
            self.data.get("todayDate")
            == now.astimezone(SCHEDULE_TIME_ZONE).date().isoformat()
            and self.data.get("todayStatus") == "EmergencyShutdowns"
        ):
            return "emergency"
        return schedule_day_status(self.data, "today", now)

    @callback
    def _handle_source_update(self) -> None:
        self.data = AlertsEnergyApi.select_schedule(
            self.source.data or [], self._operator, self._queue
        )
        self.last_update_success = self.source.last_update_success
        self.last_exception = self.source.last_exception
        self.async_update_listeners()

    async def async_refresh(self) -> None:
        await self.source.async_refresh()

    async def async_request_refresh(self) -> None:
        await self.source.async_request_refresh()

    async def async_shutdown(self) -> None:
        if not self._closed:
            self._closed = True
            self._unsub_source()
            self.source.async_update_polling_schedule()
            await async_release_area(self.hass, self.source)
        await super().async_shutdown()
