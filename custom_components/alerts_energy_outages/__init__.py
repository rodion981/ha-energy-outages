"""Alerts Energy Outages integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import async_get_api
from .const import (
    CONF_AREA,
    CONF_SCAN_INTERVAL,
    DEFAULT_AREA,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .coordinator import AlertsEnergyCoordinator, async_acquire_area, async_release_area

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.EVENT, Platform.CALENDAR]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Add the historical Kyiv area without changing registry identity."""
    if entry.version > 1:
        return False
    _normalize_options(hass, entry)
    if entry.minor_version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_AREA: DEFAULT_AREA, "area_name": "Київ", **entry.data},
            minor_version=2,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alerts Energy from a config entry."""
    _normalize_options(hass, entry)
    api = await async_get_api(hass)
    source = await async_acquire_area(
        hass, api, entry.data.get(CONF_AREA, DEFAULT_AREA)
    )
    coordinator = None
    try:
        coordinator = AlertsEnergyCoordinator(hass, source, entry)
        hass.data[DOMAIN][entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
        else:
            await async_release_area(hass, source)
        raise
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reschedule shared polling in place, without reloading entities."""
    _normalize_options(hass, entry)
    if coordinator := hass.data.get(DOMAIN, {}).get(entry.entry_id):
        coordinator.source.async_update_polling_schedule()


def _normalize_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise legacy sub-minimum intervals without changing entry identities."""
    if (
        entry.options.get(CONF_SCAN_INTERVAL, MIN_SCAN_INTERVAL_MINUTES)
        < MIN_SCAN_INTERVAL_MINUTES
    ):
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL_MINUTES},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if coordinator := hass.data.get(DOMAIN, {}).pop(entry.entry_id, None):
            await coordinator.async_shutdown()
    return unload_ok
