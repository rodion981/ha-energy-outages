"""Read-only calendar of published outage coverage, without extra API calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_ENTITY_UNIQUE_ID, DOMAIN, SITE_URL
from .coordinator import AlertsEnergyCoordinator, schedule_day_status
from .forecast import dated_outage_periods, interval_outage_type, utc_midnight
from .schedule import normalize_day


@dataclass(frozen=True, kw_only=True)
class CalendarPeriod:
    """Keep finite published coverage separate from known outage boundaries."""

    start: datetime
    end: datetime
    start_known: bool
    end_known: bool
    outage_type: str


def calendar_periods(data: dict[str, Any]) -> list[CalendarPeriod]:
    """Use each published day independently and merge continuous intervals."""
    periods: list[tuple[datetime, datetime]] = []
    starts: set[datetime] = set()
    ends: set[datetime] = set()
    for day in ("today", "tomorrow"):
        if schedule_day_status(data, day) != "published":
            continue
        day_date = date.fromisoformat(data[f"{day}Date"])
        starts.add(utc_midnight(day_date))
        ends.add(utc_midnight(day_date + timedelta(days=1)))
        periods.extend(
            dated_outage_periods(normalize_day(data, day).combined, day_date)
        )
    merged: list[tuple[datetime, datetime]] = []
    for start, end in periods:
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return [
        CalendarPeriod(
            start=start,
            end=end,
            start_known=start not in starts - ends,
            end_known=end not in ends - starts,
            outage_type=interval_outage_type(data, start, end),
        )
        for start, end in merged
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add one read-only calendar to the existing queue device."""
    async_add_entities([AlertsEnergyCalendar(hass.data[DOMAIN][entry.entry_id], entry)])


class AlertsEnergyCalendar(CoordinatorEntity[AlertsEnergyCoordinator], CalendarEntity):
    """Expose only the currently published dates, rather than guessed history."""

    _attr_has_entity_name = True
    _attr_translation_key = "outage_calendar"
    _attr_icon = "mdi:calendar-alert"
    _attr_supported_features = 0

    def __init__(
        self, coordinator: AlertsEnergyCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        identity = (
            entry.data.get(CONF_ENTITY_UNIQUE_ID) or entry.unique_id or entry.entry_id
        )
        self._attr_unique_id = f"{identity}_outage_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identity)},
            "name": entry.title,
            "manufacturer": "Alerts Energy",
            "configuration_url": f"{SITE_URL}/{quote(coordinator.area, safe='')}",
        }
        self._queue = entry.data["queue"]
        self._location = entry.data.get("locality_name") or entry.data.get("area_name")

    @property
    def available(self) -> bool:
        return super().available and any(
            schedule_day_status(self.coordinator.data, day) == "published"
            for day in ("today", "tomorrow")
        )

    @property
    def _upcoming_period(self) -> CalendarPeriod | None:
        if not self.available:
            return None
        now = dt_util.utcnow()
        return next(
            (
                period
                for period in calendar_periods(self.coordinator.data)
                if period.end > now
            ),
            None,
        )

    def _calendar_event(self, period: CalendarPeriod) -> CalendarEvent:
        uk = self.hass.config.language == "uk"
        summary = (
            f"Планове відключення · черга {self._queue}"
            if uk
            else f"Scheduled outage · queue {self._queue}"
        )
        description = [
            "Опублікований графік Alerts Energy. Фактичне електропостачання може відрізнятися."
            if uk
            else "Published Alerts Energy schedule. Actual power supply may differ."
        ]
        if period.outage_type in {"possible", "mixed"}:
            label = (
                (
                    "Можливе відключення"
                    if period.outage_type == "possible"
                    else "Планове й можливе відключення"
                )
                if uk
                else (
                    "Possible outage"
                    if period.outage_type == "possible"
                    else "Planned and possible outage"
                )
            )
            summary = f"{label} · {self._queue}"
            description.append(
                "Можливі інтервали враховано для планування; їх застосування не гарантоване."
                if uk
                else "Conditional intervals are included for planning; their application is not guaranteed."
            )
        if not period.start_known:
            description.append(
                "Початок події є межею опублікованого графіка; відключення могло початися раніше."
                if uk
                else "The event starts at the published coverage boundary; the outage may have started earlier."
            )
        if not period.end_known:
            description.append(
                "Кінець події є межею опублікованого графіка, а не підтвердженим часом відновлення."
                if uk
                else "The event ends at the published coverage boundary, not a confirmed restoration time."
            )
        return CalendarEvent(
            start=period.start,
            end=period.end,
            summary=summary,
            description="\n".join(description),
            location=self._location,
            uid=f"{self.unique_id}_{int(period.start.timestamp())}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        if period := self._upcoming_period:
            return self._calendar_event(period)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        period = self._upcoming_period
        return {
            "today_schedule_status": schedule_day_status(
                self.coordinator.data, "today"
            ),
            "tomorrow_schedule_status": schedule_day_status(
                self.coordinator.data, "tomorrow"
            ),
            "event_start_known": period.start_known if period else None,
            "event_end_known": period.end_known if period else None,
            "outage_type": period.outage_type if period else None,
        }

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return complete events intersecting [start, end), without network I/O."""
        if not self.available:
            raise HomeAssistantError("Published outage schedules are unavailable")
        if start_date >= end_date:
            return []
        return [
            self._calendar_event(period)
            for period in calendar_periods(self.coordinator.data)
            if period.start < end_date and period.end > start_date
        ]
