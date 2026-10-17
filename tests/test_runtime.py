"""Real HA setup, registry, availability, clock updates and reload tests."""

from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_OPERATOR,
    DOMAIN,
)
from custom_components.alerts_energy_outages.diagnostics import (
    async_get_config_entry_diagnostics,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)
QUEUES = "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_queues"


def entity_ids(hass, entry):
    registry = er.async_get(hass)
    return {
        item.unique_id.rsplit("_", 1)[-1]: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_setup_registry_reload(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        assert len(ids) == 8
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
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert hass.states.get(ids["today"]).state != "unavailable"
    assert hass.states.get(ids["tomorrow"]).state == "unavailable"
    assert hass.states.get(ids["now"]).state == "on"


async def test_transport_failure_recovery(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert all(
            hass.states.get(item).state == "unavailable"
            for key, item in ids.items()
            if key not in {"status", "update"}
        )
        fetch.side_effect = None
        await coordinator.async_refresh()
        assert hass.states.get(ids["now"]).state == "on"


async def test_missing_queue_loads_unavailable(hass, entry):
    with patch(
        FETCH,
        return_value=[],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert len(ids) == 8
    assert all(
        hass.states.get(item).state == "unavailable"
        for key, item in ids.items()
        if key not in {"status", "update"}
    )


async def test_first_refresh_retry(hass, entry):
    with patch(FETCH, side_effect=AlertsEnergyApiError("offline")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    assert entry.state.value == "setup_retry"


async def test_clock_boundary_without_network(hass, entry, schedule, freezer):
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 60})
    with patch(FETCH, return_value=[schedule]) as fetch:
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
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entity_ids(hass, entry)
        boundary = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert all(
            hass.states.get(item).state == "unavailable"
            for key, item in ids.items()
            if key not in {"status", "update"}
        )


async def test_reconfigure_preserves_registry(hass, entry, schedule, directory):
    with patch(FETCH, return_value=[schedule]), patch(QUEUES, return_value=["2.1"]):
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
            data={"area": "kyiv"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"operator": DEFAULT_OPERATOR}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"queue": "2.1"}
        )
        await hass.async_block_till_done()
        assert result["reason"] == "reconfigure_successful"
        assert entity_ids(hass, entry) == ids
        assert (
            len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id))
            == 8
        )
        assert (
            dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0].id
            == device_id
        )
        assert hass.states.get(ids["today"]).attributes["queue"] == "2.1"


async def test_long_state_full_attributes(hass, entry, schedule):
    schedule["today"] = [2] * 24
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get(entity_ids(hass, entry)["today"])
    assert len(state.state) <= 255
    assert len(state.attributes["periods"]) == 24


async def test_diagnostics_allowlist(hass, entry, schedule):
    schedule["private_extra"] = "do not export"
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert set(result) == {
        "area",
        "data_status",
        "last_successful_update",
        "last_update_success",
        "operator",
        "queue",
        "days",
    }
    assert result["days"]["today"]["status"] == "published"
    assert "private_extra" not in str(result)


async def test_source_timezone_is_independent(hass, entry, schedule):
    await hass.config.async_set_time_zone("America/New_York")
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_ids(hass, entry)["now"]).state == "on"


async def test_ukrainian_zero_outage_state(hass, entry, schedule):
    hass.config.language = "uk"
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert (
        hass.states.get(entity_ids(hass, entry)["tomorrow"]).state == "Без відключень"
    )


async def test_regional_api_setup_and_device_url(hass, directory):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Буча",
        unique_id="kyivska-oblast_regional_operator_2.2",
        minor_version=2,
        data={
            "area": "kyivska-oblast",
            "area_name": "Київська область",
            "operator": "regional_operator",
            "queue": "2.2",
            "locality_id": directory["city"]["katottg"],
            "locality_name": "Буча",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert hass.states.get(ids["today"]).state == "12:00–12:30"
    assert hass.states.get(ids["today"]).attributes["area"] == "kyivska-oblast"
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert devices[0].configuration_url == "https://alerts.energy/kyivska-oblast"
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["area"] == "kyivska-oblast"
    assert "locality_id" not in diagnostics
    assert "locality_name" not in diagnostics
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entity_ids(hass, entry) == ids


async def test_reconfigure_to_other_area_keeps_registry(hass, entry, directory):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    old_unique_id = entry.unique_id
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    device_id = devices[0].id
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data={"area": "kyivska-oblast"},
    )
    for data in [
        {"locality": "__skip__"},
        {"operator": "regional_operator"},
        {"queue": "2.1"},
    ]:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["entity_unique_id"] == old_unique_id
    assert entity_ids(hass, entry) == ids
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].id == device_id
    assert devices[0].configuration_url == "https://alerts.energy/kyivska-oblast"
    assert hass.states.get(ids["today"]).attributes["operator"] == "regional_operator"
    assert hass.states.get(ids["today"]).attributes["area"] == "kyivska-oblast"


async def test_legacy_migration_preserves_data(hass, entry):
    from custom_components.alerts_energy_outages import async_migrate_entry

    previous = dict(entry.data)
    unique_id = entry.unique_id
    assert await async_migrate_entry(hass, entry)
    assert entry.minor_version == 2
    assert entry.version == 1
    assert entry.unique_id == unique_id
    assert all(entry.data[key] == value for key, value in previous.items())
    assert entry.data["area"] == "kyiv"
    migrated = dict(entry.data)
    assert await async_migrate_entry(hass, entry)
    assert entry.data == migrated


async def test_migration_does_not_replace_existing_area(hass, entry):
    from custom_components.alerts_energy_outages import async_migrate_entry

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "area": "kyivska-oblast", "area_name": "Київська область"},
    )
    assert await async_migrate_entry(hass, entry)
    assert entry.data["area"] == "kyivska-oblast"
    assert entry.data["area_name"] == "Київська область"


async def test_migration_rejects_future_major(hass, entry):
    from custom_components.alerts_energy_outages import async_migrate_entry

    hass.config_entries.async_update_entry(entry, version=2)
    previous = dict(entry.data)
    assert not await async_migrate_entry(hass, entry)
    assert entry.data == previous


async def test_no_shutdowns_operator_state(hass, entry, schedule):
    schedule.update(today=[0] * 24, todayStatus="NoShutdowns")
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    assert hass.states.get(ids["today"]).state == "No outages"
    assert hass.states.get(ids["now"]).state == "off"
