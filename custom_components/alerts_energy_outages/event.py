"""Schedule changes observed through the existing regional poller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENTITY_UNIQUE_ID,
    DEFAULT_OPERATOR,
    DOMAIN,
    SCHEDULE_TIME_ZONE,
    SITE_URL,
)
from .coordinator import (
    AlertsEnergyCoordinator,
    format_boundary,
    outage_periods,
    period_attributes,
    schedule_day_status,
)
from .schedule import DaySchedule, normalize_day


def _slots(hours: list[int]) -> set[int]:
    """Normalize the existing codes without comparing source timestamps."""
    return {slot for start, end in outage_periods(hours) for slot in range(start, end)}


def _periods(slots: set[int]) -> list[dict[str, str]]:
    """Merge consecutive half hours, preserving the 24:00 boundary."""
    result: list[dict[str, str]] = []
    for slot in sorted(slots):
        if result and result[-1]["end"] == format_boundary(slot):
            result[-1]["end"] = format_boundary(slot + 1)
        else:
            result.append(
                {"start": format_boundary(slot), "end": format_boundary(slot + 1)}
            )
    return result


@dataclass
class ScheduleChangeStoredData(ExtraStoredData):
    """Retain bounded comparison snapshots alongside HA's restored event."""

    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return self.data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a change event to the existing queue device."""
    async_add_entities(
        [AlertsEnergyScheduleChangeEvent(hass.data[DOMAIN][entry.entry_id], entry)]
    )


class AlertsEnergyScheduleChangeEvent(
    CoordinatorEntity[AlertsEnergyCoordinator], EventEntity
):
    """Emit one event per observed update, including both changed days."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule_changed"
    _attr_event_types = ["schedule_changed"]
    _attr_icon = "mdi:calendar-sync"

    def __init__(
        self, coordinator: AlertsEnergyCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        identity = (
            entry.data.get(CONF_ENTITY_UNIQUE_ID) or entry.unique_id or entry.entry_id
        )
        self._attr_unique_id = f"{identity}_schedule_changed"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identity)},
            "name": entry.title,
            "manufacturer": "Alerts Energy",
            "configuration_url": f"{SITE_URL}/{quote(coordinator.area, safe='')}",
        }
        self._identity = [
            coordinator.area,
            entry.data.get("operator", DEFAULT_OPERATOR),
            entry.data["queue"],
        ]
        self._snapshots: dict[str, DaySchedule] = {}
        self._ready = False

    @property
    def available(self) -> bool:
        """Keep the last event stable during failures, without recovery replays."""
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if restored := await self.async_get_last_extra_data():
            data = restored.as_dict()
            snapshots = data.get("schedules")
            if data.get("schedule_identity") == self._identity and isinstance(
                snapshots, dict
            ):
                for date, snapshot in snapshots.items():
                    if isinstance(snapshot, list):
                        # Compatibility with the initial planned-only snapshots.
                        snapshot = {"planned": snapshot, "possible": []}
                    if not isinstance(snapshot, dict):
                        continue
                    try:
                        self._snapshots[date] = normalize_day(
                            {
                                "day": snapshot.get("planned"),
                                "dayPossible": snapshot.get("possible", []),
                            },
                            "day",
                        )
                    except ValueError:
                        continue
        # Loading/reconfiguring establishes a quiet baseline. Retain restored
        # published days if the source is temporarily missing or invalid.
        self._capture_changes(notify=False)
        self._ready = True

    @property
    def extra_restore_state_data(self) -> ScheduleChangeStoredData:
        return ScheduleChangeStoredData(
            {
                **super().extra_restore_state_data.as_dict(),
                "schedule_identity": self._identity,
                "schedules": {
                    date: snapshot.as_dict()
                    for date, snapshot in self._snapshots.items()
                },
            }
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._ready:
            self._capture_changes(notify=True)

    @callback
    def _capture_changes(self, *, notify: bool) -> None:
        """Compare only complete, published schedules by calendar date."""
        today = dt_util.utcnow().astimezone(SCHEDULE_TIME_ZONE).date()
        dates = {today.isoformat(), (today + timedelta(days=1)).isoformat()}
        self._snapshots = {
            date: snapshot
            for date, snapshot in self._snapshots.items()
            if date in dates
        }
        if not self.coordinator.last_update_success:
            return
        data = self.coordinator.data
        changes = []
        for day in ("today", "tomorrow"):
            if schedule_day_status(data, day) != "published":
                continue
            date = data[f"{day}Date"]
            schedule = normalize_day(data, day)
            previous = self._snapshots.get(date)
            self._snapshots[date] = schedule
            if not notify or previous == schedule:
                continue
            before = _slots(previous.combined) if previous is not None else set()
            after = _slots(schedule.combined)
            changes.append(
                {
                    "date": date,
                    "change_type": "published" if previous is None else "changed",
                    "before": _periods(before) if previous is not None else None,
                    "after": _periods(after),
                    "added": _periods(after - before),
                    "removed": _periods(before - after),
                    "planned": period_attributes(schedule.planned),
                    "possible": period_attributes(schedule.possible),
                    "previous_planned": period_attributes(previous.planned)
                    if previous
                    else None,
                    "previous_possible": period_attributes(previous.possible)
                    if previous
                    else None,
                    "classification_changed": previous is not None and before == after,
                }
            )
        if changes:
            self._trigger_event(
                "schedule_changed",
                {
                    "area": self._identity[0],
                    "operator": self._identity[1],
                    "queue": self._identity[2],
                    "changes": changes,
                },
            )
            self.async_write_ha_state()
