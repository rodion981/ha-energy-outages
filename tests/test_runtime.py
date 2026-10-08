"""Real HA setup, registry, availability, clock updates and reload tests."""

from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import DEFAULT_OPERATOR, DOMAIN
from custom_components.alerts_energy_outages.diagnostics import (
    async_get_config_entry_diagnostics,
)

FETCH = "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedule"
QUEUES = "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_queues"


def entity_ids(hass, entry):
    registry = er.async_get(hass)
    return {
        item.unique_id.rsplit("_", 1)[-1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_setup_registry_reload(hass, entry, schedule):
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        assert len(ids) == 3
        assert hass.states.get(ids["today"]).state == "12:00–12:30"
        assert hass.states.get(ids["tomorrow"]).state == "No outages"
        binary = hass.states.get(ids["now"])
        assert binary.state == "on"
        assert binary.attributes["device_class"] == "problem"
        devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        assert len(devices) == 1
        device_id = devices[0].id
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.entry_id not in hass.data[DOMAIN]
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entity_ids(hass, entry) == ids
        assert (
            dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
            == device_id
        )


async def test_independent_days(hass, entry, schedule):
    schedule["tomorrow"] = []
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert hass.states.get(ids["today"]).state != "unavailable"
    assert hass.states.get(ids["tomorrow"]).state == "unavailable"
    assert hass.states.get(ids["now"]).state == "on"


async def test_transport_failure_recovery(hass, entry, schedule):
    with patch(FETCH, return_value=schedule) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert all(
            hass.states.get(item).state == "unavailable" for item in ids.values()
        )
        fetch.side_effect = None
        await coordinator.async_refresh()
        assert hass.states.get(ids["now"]).state == "on"


async def test_missing_queue_loads_unavailable(hass, entry):
    with patch(
        FETCH,
        return_value={
            "queue": "2.2",
            "initiator": DEFAULT_OPERATOR,
            "schedule_found": False,
        },
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert len(ids) == 3
    assert all(hass.states.get(item).state == "unavailable" for item in ids.values())


async def test_first_refresh_retry(hass, entry):
    with patch(FETCH, side_effect=AlertsEnergyApiError("offline")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    assert entry.state.value == "setup_retry"


async def test_clock_boundary_without_network(hass, entry, schedule, freezer):
    with (
        patch(FETCH, return_value=schedule) as fetch,
        patch(
            "custom_components.alerts_energy_outages.coordinator.SCAN_INTERVAL_SECONDS",
            3600,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        calls = fetch.call_count
        boundary = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert hass.states.get(ids["now"]).state == "off"
        assert fetch.call_count == calls


async def test_midnight_marks_stale(hass, entry, schedule, freezer):
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        boundary = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert all(
            hass.states.get(item).state == "unavailable" for item in ids.values()
        )


async def test_reconfigure_preserves_registry(hass, entry, schedule):
    with patch(FETCH, return_value=schedule), patch(QUEUES, return_value=["2.1"]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        device_id = dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )[0].id
        schedule["queue"] = "2.1"
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={"queue": "2.1"},
        )
        await hass.async_block_till_done()
        assert result["reason"] == "reconfigure_successful"
        assert entity_ids(hass, entry) == ids
        assert (
            len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id))
            == 3
        )
        assert (
            dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
            == device_id
        )
        assert hass.states.get(ids["today"]).attributes["queue"] == "2.1"


async def test_long_state_full_attributes(hass, entry, schedule):
    schedule["today"] = [2] * 24
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get(entity_ids(hass, entry)["today"])
    assert len(state.state) <= 255
    assert len(state.attributes["periods"]) == 24


async def test_diagnostics_allowlist(hass, entry, schedule):
    schedule["private_extra"] = "do not export"
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert set(result) == {"last_update_success", "operator", "queue", "days"}
    assert result["days"]["today"]["status"] == "published"
    assert "private_extra" not in str(result)


async def test_source_timezone_is_independent(hass, entry, schedule):
    await hass.config.async_set_time_zone("America/New_York")
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_ids(hass, entry)["now"]).state == "on"


async def test_ukrainian_zero_outage_state(hass, entry, schedule):
    hass.config.language = "uk"
    with patch(FETCH, return_value=schedule):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert (
        hass.states.get(entity_ids(hass, entry)["tomorrow"]).state == "Без відключень"
    )
