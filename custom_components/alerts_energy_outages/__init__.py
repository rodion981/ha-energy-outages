"""Alerts Energy Outages integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change

from .api import AlertsEnergyApi
from .const import CONF_AREA, DEFAULT_AREA, DOMAIN
from .coordinator import AlertsEnergyCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Add the historical Kyiv area without changing registry identity."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_AREA: DEFAULT_AREA, "area_name": "Київ", **entry.data},
            minor_version=2,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alerts Energy from a config entry."""
    api = AlertsEnergyApi(async_get_clientsession(hass))
    coordinator = AlertsEnergyCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def update_time_dependent_entities(_now: datetime) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_utc_time_change(
            hass, update_time_dependent_entities, minute=[0, 30], second=0
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
