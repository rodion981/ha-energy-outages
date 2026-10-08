"""Diagnostics without exporting the full third-party response."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AlertsEnergyCoordinator, schedule_day_status


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Expose only update health and public schedule metadata."""
    coordinator: AlertsEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    return {
        "last_update_success": coordinator.last_update_success,
        "operator": entry.data["operator"],
        "queue": entry.data["queue"],
        "days": {
            day: {
                "status": schedule_day_status(data, day),
                "date": data.get(f"{day}Date"),
                "source_status": data.get(f"{day}Status"),
            }
            for day in ("today", "tomorrow")
        },
    }
