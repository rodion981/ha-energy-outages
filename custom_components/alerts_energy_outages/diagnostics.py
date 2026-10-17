"""Diagnostics without exporting the full third-party response."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AlertsEnergyCoordinator, schedule_day_status
from .schedule import normalize_day


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Expose only update health and public schedule metadata."""
    coordinator: AlertsEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    return {
        "area": coordinator.area,
        "data_status": coordinator.data_status,
        "last_successful_update": (
            coordinator.last_successful_update.isoformat()
            if coordinator.last_successful_update
            else None
        ),
        "last_update_success": coordinator.last_update_success,
        "data_is_cached": coordinator.data_is_cached,
        "operator": entry.data["operator"],
        "queue": entry.data["queue"],
        "days": {
            day: {
                "status": schedule_day_status(data, day),
                "date": data.get(f"{day}Date"),
                "source_status": data.get(f"{day}Status"),
                "outage_type": normalize_day(data, day).outage_type
                if schedule_day_status(data, day) == "published"
                else None,
            }
            for day in ("today", "tomorrow")
        },
    }
