"""Binary sensors for Alerts Energy outages."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_ENTITY_UNIQUE_ID, DOMAIN, SCHEDULE_TIME_ZONE, SITE_URL
from .coordinator import AlertsEnergyCoordinator, schedule_day_status
from .schedule import normalize_day


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the current-outage sensor."""
    coordinator: AlertsEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AlertsEnergyOutageNow(coordinator, entry)])


class AlertsEnergyOutageNow(
    CoordinatorEntity[AlertsEnergyCoordinator],
    BinarySensorEntity,
):
    """Whether the selected queue is currently scheduled off."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = True
    _attr_icon = "mdi:power-plug-off"
    _attr_translation_key = "outage_now"

    def __init__(
        self,
        coordinator: AlertsEnergyCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        identity = (
            entry.data.get(CONF_ENTITY_UNIQUE_ID) or entry.unique_id or entry.entry_id
        )
        self._attr_unique_id = f"{identity}_outage_now"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identity)},
            "name": entry.title,
            "manufacturer": "Alerts Energy",
            "configuration_url": f"{SITE_URL}/{quote(coordinator.area, safe='')}",
        }

    @property
    def available(self) -> bool:
        """Require a successful update and a published schedule for today."""
        return (
            super().available
            and schedule_day_status(self.coordinator.data, "today") == "published"
        )

    @property
    def is_on(self) -> bool | None:
        """Return true when the current half hour is an outage."""
        if not self.available:
            return None
        return self.extra_state_attributes["outage_type"] != "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Distinguish conditional intervals from planned ones without I/O."""
        if not self.available:
            return {"outage_type": None, "planned_now": None, "possible_now": None}
        now = dt_util.utcnow().astimezone(SCHEDULE_TIME_ZONE)
        boundary = now.hour * 2 + now.minute // 30
        schedule = normalize_day(self.coordinator.data, "today")
        half_code = 2 if boundary % 2 == 0 else 3
        return {
            "outage_type": schedule.slot_type(boundary),
            "planned_now": schedule.planned[boundary // 2] in (1, half_code),
            "possible_now": schedule.possible[boundary // 2] in (1, half_code),
        }
