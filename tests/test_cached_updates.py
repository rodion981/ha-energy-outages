"""Retain dated schedules and retry failed shared updates without entity gaps."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_OPERATOR,
    DOMAIN,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)


def entities(hass, entry):
    return {
        item.unique_id.removeprefix(entry.unique_id + "_"): item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


@pytest.mark.parametrize("reason", ["connection_error", "invalid"])
async def test_cached_schedule_survives_transport_failure(
    hass, entry, schedule, reason
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        before = {key: hass.states.get(entity).state for key, entity in ids.items()}
        fetch.side_effect = AlertsEnergyApiError("offline", reason=reason)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        for key, entity in ids.items():
            if key != "data_status":
                assert hass.states.get(entity).state == before[key]
            if key not in {"last_successful_update", "schedule_changed"}:
                assert hass.states.get(entity).attributes["data_is_cached"] is True
        assert not coordinator.last_update_success
        assert hass.states.get(ids["data_status"]).state == reason
        fetch.side_effect = None
        await coordinator.async_refresh()
        for key, entity in ids.items():
            if key not in {"last_successful_update", "schedule_changed"}:
                assert hass.states.get(entity).attributes["data_is_cached"] is False


async def advance(hass, freezer, seconds):
    now = dt_util.utcnow() + timedelta(seconds=seconds)
    freezer.move_to(now)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()


async def test_scheduled_failure_respects_minimum_then_restores_interval(
    hass, entry, schedule, freezer
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        source = hass.data[DOMAIN][entry.entry_id].source
        assert source.update_interval == timedelta(minutes=15)
        fetch.side_effect = AlertsEnergyApiError("offline")
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 2
        assert not source.last_update_success
        assert source.update_interval == timedelta(minutes=15)
        # A second failed retry still keeps only one regional timer.
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 3
        fetch.side_effect = None
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 4
        assert source.last_update_success
        assert source.update_interval == timedelta(minutes=15)
        await advance(hass, freezer, 2 * 60)
        assert fetch.call_count == 4
        await advance(hass, freezer, 13 * 60 + 5)
        assert fetch.call_count == 5


@pytest.mark.parametrize("minutes", [15, 60, 1440])
async def test_recovery_preserves_configured_interval(
    hass, entry, schedule, freezer, minutes
):
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: minutes})
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert coordinator.source.update_interval == timedelta(minutes=minutes)
        fetch.side_effect = None
        await advance(hass, freezer, minutes * 60 + 5)
        assert fetch.call_count == 3
        assert coordinator.source.update_interval == timedelta(minutes=minutes)
        assert entry.options[CONF_SCAN_INTERVAL] == minutes


async def test_cached_clock_updates_and_date_expiry_with_polling_disabled(
    hass, entry, schedule, freezer
):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert hass.states.get(ids["outage_now"]).state == "on"
        await advance(hass, freezer, 30 * 60)
        assert hass.states.get(ids["outage_now"]).state == "off"
        assert hass.states.get(ids["outage_now"]).attributes["data_is_cached"]
        assert fetch.call_count == 2
        midnight = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(midnight)
        async_fire_time_changed(hass, midnight)
        await hass.async_block_till_done()
        for key, entity in ids.items():
            if key not in {"data_status", "last_successful_update", "schedule_changed"}:
                assert hass.states.get(entity).state == "unavailable"
        assert fetch.call_count == 2


@pytest.mark.parametrize("kind", ["missing", "invalid", "stale", "emergency"])
async def test_new_unusable_response_does_not_resurrect_previous_schedule(
    hass, entry, schedule, kind
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        bad = deepcopy(schedule)
        bad["tomorrow"] = []
        if kind == "invalid":
            bad["today"][0] = -1
        elif kind == "stale":
            bad["todayDate"] = "2026-10-06"
        elif kind == "emergency":
            bad["todayStatus"] = "EmergencyShutdowns"
        fetch.return_value = [] if kind == "missing" else [bad]
        await coordinator.async_refresh()
        assert not coordinator.data_is_cached
        assert hass.states.get(ids["today"]).state == "unavailable"
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert hass.states.get(ids["today"]).state == "unavailable"
        assert hass.states.get(ids["outage_now"]).state == "unavailable"
        assert hass.states.get(ids["outage_calendar"]).state == "unavailable"


async def test_published_tomorrow_remains_independent_during_failure(
    hass, entry, schedule
):
    schedule["today"] = []
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        fetch.side_effect = AlertsEnergyApiError("offline")
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["today"]).state == "unavailable"
        assert hass.states.get(ids["tomorrow"]).state == "No outages"
        assert hass.states.get(ids["tomorrow"]).attributes["data_is_cached"]
        assert hass.states.get(ids["outage_calendar"]).state == "off"


async def test_shared_retry_respects_option_changes_and_final_unload(
    hass, entry, schedule, freezer
):
    row = {**schedule, "queue": "2.1"}
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other queue",
        unique_id=f"{DEFAULT_OPERATOR}_2.1",
        minor_version=2,
        data={"operator": DEFAULT_OPERATOR, "queue": "2.1"},
        options={CONF_SCAN_INTERVAL: 5},
    )
    with patch(FETCH, return_value=[schedule, row]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        other.add_to_hass(hass)
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.source is hass.data[DOMAIN][other.entry_id].source
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        hass.config_entries.async_update_entry(other, options={CONF_SCAN_INTERVAL: 3})
        await hass.async_block_till_done()
        assert coordinator.source.update_interval == timedelta(minutes=15)
        fetch.side_effect = None
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 3
        assert coordinator.source.update_interval == timedelta(minutes=15)
        assert await hass.config_entries.async_unload(other.entry_id)
        await hass.async_block_till_done()
        assert coordinator.source.update_interval == timedelta(minutes=15)
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 4
