"""Sensors for Alerts Energy outage schedules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_ENTITY_UNIQUE_ID, DOMAIN, SITE_URL
from .coordinator import (
    AlertsEnergyCoordinator,
    format_periods,
    outage_periods,
    period_attributes,
    schedule_day_status,
)
from .forecast import ScheduleForecast, schedule_forecast
from .schedule import normalize_day
from .source import source_checked_at


@dataclass(frozen=True, kw_only=True)
class AlertsEnergySensorDescription(SensorEntityDescription):
    """Describe an Alerts Energy sensor."""

    value_fn: Callable[[dict[str, Any], str], str]


DESCRIPTIONS = (
    AlertsEnergySensorDescription(
        key="today",
        translation_key="today",
        icon="mdi:calendar-today",
        value_fn=lambda data, label: format_periods(
            outage_periods(normalize_day(data, "today").combined), label
        ),
    ),
    AlertsEnergySensorDescription(
        key="tomorrow",
        translation_key="tomorrow",
        icon="mdi:calendar-clock",
        value_fn=lambda data, label: format_periods(
            outage_periods(normalize_day(data, "tomorrow").combined), label
        ),
    ),
)

FORECAST_DESCRIPTIONS = (
    SensorEntityDescription(
        key="next_outage",
        translation_key="next_outage",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:power-plug-off",
    ),
    SensorEntityDescription(
        key="expected_restoration",
        translation_key="expected_restoration",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="outage_duration",
        translation_key="outage_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
    ),
)

INFORMATION_DESCRIPTIONS = (
    SensorEntityDescription(
        key="data_status",
        translation_key="data_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "published",
            "unpublished",
            "stale",
            "invalid",
            "not_found",
            "connection_error",
            "emergency",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="last_successful_update",
        translation_key="last_successful_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:update",
    ),
    *(
        SensorEntityDescription(
            key=f"{day}_checked_at",
            translation_key=f"{day}_checked_at",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:clipboard-check-outline",
        )
        for day in ("today", "tomorrow")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up schedule sensors."""
    coordinator: AlertsEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            *(
                AlertsEnergySensor(coordinator, entry, description)
                for description in DESCRIPTIONS
            ),
            *(
                AlertsEnergyForecastSensor(coordinator, entry, description)
                for description in FORECAST_DESCRIPTIONS
            ),
            *(
                AlertsEnergyInformationSensor(coordinator, entry, description)
                for description in INFORMATION_DESCRIPTIONS
            ),
        ]
    )


class AlertsEnergySensorBase(
    CoordinatorEntity[AlertsEnergyCoordinator],
    SensorEntity,
):
    """Retain the same entry/device identity for old and additive sensor keys."""

    entity_description: SensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AlertsEnergyCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        identity = (
            entry.data.get(CONF_ENTITY_UNIQUE_ID) or entry.unique_id or entry.entry_id
        )
        self._attr_unique_id = f"{identity}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identity)},
            "name": entry.title,
            "manufacturer": "Alerts Energy",
            "configuration_url": f"{SITE_URL}/{quote(coordinator.area, safe='')}",
        }

    @property
    def available(self) -> bool:
        """Keep retained data usable; subclasses still validate published dates."""
        return self.coordinator.data is not None


class AlertsEnergySensor(AlertsEnergySensorBase):
    """Representation of an Alerts Energy schedule."""

    entity_description: AlertsEnergySensorDescription

    @property
    def available(self) -> bool:
        """Keep each day's availability independent and date aware."""
        return (
            super().available
            and schedule_day_status(self.coordinator.data, self.entity_description.key)
            == "published"
        )

    @property
    def native_value(self) -> str | None:
        """Return the formatted schedule."""
        if not self.available:
            return None
        no_outages = (
            "Без відключень" if self.hass.config.language == "uk" else "No outages"
        )
        result = self.entity_description.value_fn(self.coordinator.data, no_outages)
        kind = normalize_day(
            self.coordinator.data, self.entity_description.key
        ).outage_type
        uk = self.hass.config.language == "uk"
        if kind in {"possible", "mixed"}:
            prefix = (
                ("Можливі" if kind == "possible" else "Планові й можливі")
                if uk
                else ("Possible" if kind == "possible" else "Planned and possible")
            )
            result = f"{prefix}: {result}"
        return result if len(result) <= 255 else result[:254] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose source data for dashboards and automations."""
        day = self.entity_description.key
        hours = self.coordinator.data.get(day)
        status = schedule_day_status(self.coordinator.data, day)
        schedule = (
            normalize_day(self.coordinator.data, day) if status == "published" else None
        )
        return {
            "data_is_cached": self.coordinator.data_is_cached,
            "area": self.coordinator.area,
            "queue": self.coordinator.data["queue"],
            "operator": self.coordinator.data["initiator"],
            "updated": self.coordinator.data.get("updated"),
            "hours": hours,
            "possible_hours": self.coordinator.data.get(f"{day}Possible"),
            "date": self.coordinator.data.get(f"{day}Date"),
            "source_status": self.coordinator.data.get(f"{day}Status"),
            "schedule_status": status,
            "periods": period_attributes(schedule.combined) if schedule else [],
            "planned_periods": period_attributes(schedule.planned) if schedule else [],
            "possible_periods": period_attributes(schedule.possible)
            if schedule
            else [],
            "outage_type": schedule.outage_type if schedule else None,
        }


class AlertsEnergyForecastSensor(AlertsEnergySensorBase):
    """Published upcoming/current windows as typed timestamps and duration."""

    @property
    def available(self) -> bool:
        return (
            super().available
            and schedule_day_status(self.coordinator.data, "today") == "published"
        )

    @property
    def _forecast(self) -> ScheduleForecast:
        return schedule_forecast(self.coordinator.data, dt_util.utcnow())

    @property
    def native_value(self) -> datetime | float | None:
        if not self.available:
            return None
        forecast = self._forecast
        if self.entity_description.key == "next_outage":
            return forecast.next_outage.start if forecast.next_outage else None
        if not forecast.selected:
            return None
        if self.entity_description.key == "expected_restoration":
            return forecast.selected.end
        return forecast.selected.duration_minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        forecast = self._forecast if self.available else ScheduleForecast()
        is_next = self.entity_description.key == "next_outage"
        window = forecast.next_outage if is_next else forecast.selected
        return {
            "data_is_cached": self.coordinator.data_is_cached,
            "area": self.coordinator.area,
            "operator": self.coordinator.data["initiator"],
            "queue": self.coordinator.data["queue"],
            "outage_context": ("next" if window else "none")
            if is_next
            else forecast.context,
            "outage_type": window.outage_type if window else None,
            "outage_start": window.start.isoformat()
            if window and window.start_known
            else None,
            "outage_end": window.end.isoformat() if window and window.end else None,
            "coverage_end": forecast.coverage_end.isoformat()
            if forecast.coverage_end
            else None,
            "forecast_status": (
                "unavailable"
                if not self.available
                else "no_outages_in_published_schedule"
                if window is None
                else "end_not_published"
                if window.end is None
                else "start_not_published"
                if self.entity_description.key == "outage_duration"
                and not window.start_known
                else "scheduled"
            ),
        }


class AlertsEnergyInformationSensor(AlertsEnergySensorBase):
    """Keep health information visible during a failed network update."""

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str | datetime | None:
        if self.entity_description.key == "data_status":
            return self.coordinator.data_status
        if self.entity_description.key.endswith("_checked_at"):
            return source_checked_at(
                self.coordinator.data, self.entity_description.key.split("_", 1)[0]
            )
        return self.coordinator.last_successful_update

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "last_successful_update":
            return None
        if self.entity_description.key.endswith("_checked_at"):
            return {"data_is_cached": self.coordinator.data_is_cached}
        data = self.coordinator.data
        return {
            "data_is_cached": self.coordinator.data_is_cached,
            "today_schedule_status": schedule_day_status(data, "today"),
            "tomorrow_schedule_status": schedule_day_status(data, "tomorrow"),
            "today_source_status": data.get("todayStatus"),
            "tomorrow_source_status": data.get("tomorrowStatus"),
        }
