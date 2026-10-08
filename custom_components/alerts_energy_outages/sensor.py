"""Sensors for Alerts Energy outage schedules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITY_UNIQUE_ID, DOMAIN
from .coordinator import (
    AlertsEnergyCoordinator,
    format_periods,
    outage_periods,
    schedule_day_status,
)


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up schedule sensors."""
    coordinator: AlertsEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AlertsEnergySensor(coordinator, entry, description)
        for description in DESCRIPTIONS
    )


class AlertsEnergySensor(
    CoordinatorEntity[AlertsEnergyCoordinator],
    SensorEntity,
):
    """Representation of an Alerts Energy schedule."""

    entity_description: AlertsEnergySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AlertsEnergyCoordinator,
        entry: ConfigEntry,
        description: AlertsEnergySensorDescription,
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
            "configuration_url": "https://alerts.energy/kyiv",
        }

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
