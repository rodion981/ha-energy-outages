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
    schedule_day_status,
)
from .forecast import ScheduleForecast, schedule_forecast


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
            outage_periods(data["today"]), label
        ),
    ),
    AlertsEnergySensorDescription(
        key="tomorrow",
        translation_key="tomorrow",
        icon="mdi:calendar-clock",
        value_fn=lambda data, label: format_periods(
            outage_periods(data["tomorrow"]), label
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
        return self.entity_description.value_fn(self.coordinator.data, no_outages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose source data for dashboards and automations."""
        day = self.entity_description.key
        hours = self.coordinator.data.get(day)
        status = schedule_day_status(self.coordinator.data, day)
        periods = (
            outage_periods(self.coordinator.data[day]) if status == "published" else []
        )
        return {
            "area": self.coordinator.area,
            "queue": self.coordinator.data["queue"],
            "operator": self.coordinator.data["initiator"],
            "updated": self.coordinator.data.get("updated"),
            "hours": hours,
            "date": self.coordinator.data.get(f"{day}Date"),
            "source_status": self.coordinator.data.get(f"{day}Status"),
            "schedule_status": status,
            "periods": [
                {
                    "start": f"{start // 2:02d}:{(start % 2) * 30:02d}",
                    "end": f"{end // 2:02d}:{(end % 2) * 30:02d}",
                }
                for start, end in periods
            ],
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
            "area": self.coordinator.area,
            "operator": self.coordinator.data["initiator"],
            "queue": self.coordinator.data["queue"],
            "outage_context": ("next" if window else "none")
            if is_next
            else forecast.context,
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
        return self.coordinator.last_successful_update

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "data_status":
            return None
        data = self.coordinator.data
        return {
            "today_schedule_status": schedule_day_status(data, "today"),
            "tomorrow_schedule_status": schedule_day_status(data, "tomorrow"),
            "today_source_status": data.get("todayStatus"),
            "tomorrow_source_status": data.get("tomorrowStatus"),
        }
