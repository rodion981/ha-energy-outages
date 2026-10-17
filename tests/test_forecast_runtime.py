"""New forecast/health entities, actual timestamps and failure semantics."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import (
    API_URL,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)


def entities(hass, entry):
    prefix = entry.data.get("entity_unique_id") or entry.unique_id or entry.entry_id
    return {
        item.unique_id.removeprefix(prefix + "_"): item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


async def test_forecast_types_and_clock_transition(hass, entry, schedule, freezer):
    schedule["today"][16] = 1
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 1440})
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        assert len(ids) == 10
        next_state = hass.states.get(ids["next_outage"])
        assert next_state.attributes["device_class"] == "timestamp"
        assert datetime.fromisoformat(next_state.state) == datetime(
            2026, 10, 7, 13, tzinfo=UTC
        )
        restoration = hass.states.get(ids["expected_restoration"])
        assert datetime.fromisoformat(restoration.state) == datetime(
            2026, 10, 7, 9, 30, tzinfo=UTC
        )
        assert restoration.attributes["outage_context"] == "current"
        duration = hass.states.get(ids["outage_duration"])
        assert duration.attributes["device_class"] == "duration"
        assert duration.attributes["unit_of_measurement"] == "min"
        assert "state_class" not in duration.attributes
        assert float(duration.state) == 30
        assert hass.states.get(ids["data_status"]).state == "published"
        boundary = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert fetch.call_count == 1
        restoration = hass.states.get(ids["expected_restoration"])
        assert datetime.fromisoformat(restoration.state) == datetime(
            2026, 10, 7, 14, tzinfo=UTC
        )
        assert restoration.attributes["outage_context"] == "next"
        assert float(hass.states.get(ids["outage_duration"]).state) == 60


async def test_no_outage_has_unknown_timestamps_not_zero(hass, entry, schedule):
    schedule["today"] = [0] * 24
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    for key in ["next_outage", "expected_restoration", "outage_duration"]:
        state = hass.states.get(ids[key])
        assert state.state == "unknown"
        assert state.attributes["forecast_status"] == "no_outages_in_published_schedule"
    assert hass.states.get(ids["today"]).state == "No outages"


async def test_unpublished_end_stays_unknown(hass, entry, schedule, freezer):
    freezer.move_to(datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    schedule.update(today=[0] * 23 + [1], tomorrow=[])
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["outage_now"]).state == "on"
    for key in ["expected_restoration", "outage_duration"]:
        state = hass.states.get(ids[key])
        assert state.state == "unknown"
        assert state.attributes["forecast_status"] == "end_not_published"


async def test_unpublished_start_keeps_restoration_but_not_full_duration(
    hass, entry, schedule, freezer
):
    freezer.move_to(datetime(2026, 10, 6, 21, 15, tzinfo=UTC))
    schedule["today"][0] = 1
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    restoration = hass.states.get(ids["expected_restoration"])
    assert datetime.fromisoformat(restoration.state) == datetime(
        2026, 10, 6, 22, tzinfo=UTC
    )
    assert restoration.attributes["outage_start"] is None
    duration = hass.states.get(ids["outage_duration"])
    assert duration.state == "unknown"
    assert duration.attributes["forecast_status"] == "start_not_published"


@pytest.mark.parametrize(
    "change,status",
    [
        ({"today": []}, "unpublished"),
        ({"todayDate": "2026-10-06"}, "stale"),
        ({"today": [8] * 24}, "invalid"),
        ({"today": [9] * 24, "todayStatus": "EmergencyShutdowns"}, "emergency"),
    ],
)
async def test_visible_data_status_for_unavailable_schedule(
    hass, entry, schedule, change, status
):
    schedule.update(change)
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["data_status"]).state == status
    for key in [
        "today",
        "outage_now",
        "next_outage",
        "expected_restoration",
        "outage_duration",
    ]:
        assert hass.states.get(ids[key]).state == "unavailable"
    assert hass.states.get(ids["last_successful_update"]).state not in {
        "unknown",
        "unavailable",
    }


async def test_missing_queue_status_is_visible(hass, entry):
    with patch(FETCH, return_value=[]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["data_status"]).state == "not_found"
    assert hass.states.get(ids["today"]).state == "unavailable"


async def test_last_success_is_preserved_on_failure_then_recovers(
    hass, entry, schedule, freezer
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        stamp = hass.states.get(ids["last_successful_update"]).state
        fetch.side_effect = AlertsEnergyApiError("offline")
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["data_status"]).state == "connection_error"
        assert hass.states.get(ids["last_successful_update"]).state == stamp
        assert datetime.fromisoformat(
            hass.states.get(ids["expected_restoration"]).state
        ) == datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        assert hass.states.get(ids["expected_restoration"]).attributes["data_is_cached"]
        fetch.side_effect = None
        freezer.move_to(datetime(2026, 10, 7, 9, 1, tzinfo=UTC))
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["data_status"]).state == "published"
        assert datetime.fromisoformat(
            hass.states.get(ids["last_successful_update"]).state
        ) == datetime(2026, 10, 7, 9, 1, tzinfo=UTC)


async def test_invalid_api_payload_is_not_reported_as_network_error(
    hass, entry, aioclient_mock
):
    aioclient_mock.get(API_URL, json={})
    with patch(FETCH, return_value=[]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert hass.states.get(ids["data_status"]).state == "invalid"


@pytest.mark.parametrize("api_offline", [False, True])
async def test_timestamp_can_trigger_a_real_ha_automation(
    hass, entry, schedule, freezer, api_offline
):
    schedule["today"][12] = 3
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 1440})
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        events = []
        hass.bus.async_listen("test_outage_notice", lambda event: events.append(event))
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "alias": "Forecast timestamp trigger",
                        "trigger": [{"platform": "time", "at": ids["next_outage"]}],
                        "action": [{"event": "test_outage_notice"}],
                    }
                ]
            },
        )
        await hass.async_start()
        await hass.async_block_till_done()
        # Dispatch the startup clock tick before jumping to the outage boundary.
        # Otherwise a timer from 09:00 would unrealistically run at 09:30 first.
        initial = datetime(2026, 10, 7, 9, 0, 1, tzinfo=UTC)
        freezer.move_to(initial)
        async_fire_time_changed(hass, initial)
        await hass.async_block_till_done()
        if api_offline:
            fetch.side_effect = AlertsEnergyApiError("offline")
            await hass.data[DOMAIN][entry.entry_id].async_refresh()
            assert hass.states.get(ids["next_outage"]).attributes["data_is_cached"]
        boundary = datetime(2026, 10, 7, 9, 30, 1, tzinfo=UTC)
        freezer.move_to(boundary)
        # The HA test helper iterates a heap, not deadline order. Real asyncio
        # dispatches the timestamp trigger before the clock's fractional delay.
        # A sorted heap also remains valid for asyncio, on both HA baselines.
        hass.loop._scheduled.sort(key=lambda handle: handle.when())
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert len(events) == 1
        assert hass.states.get(ids["outage_now"]).state == "on"
        if api_offline:
            assert hass.states.get(ids["data_status"]).state == "connection_error"
