"""Shared area polling, setup races and ownership cleanup."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.alerts_energy_outages.api import (
    AlertsEnergyApi,
    AlertsEnergyApiError,
)
from custom_components.alerts_energy_outages.const import (
    DATA_AREAS,
    DEFAULT_OPERATOR,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
)
from custom_components.alerts_energy_outages.coordinator import async_acquire_area

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)


def second_entry(hass, area="kyiv", queue="2.1", disable_polling=False):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        unique_id=f"{area}_{DEFAULT_OPERATOR}_{queue}",
        minor_version=2,
        data={"area": area, "operator": DEFAULT_OPERATOR, "queue": queue},
        pref_disable_polling=disable_polling,
    )
    entry.add_to_hass(hass)
    return entry


async def test_one_request_for_multiple_queues_and_surviving_owner(
    hass, entry, schedule, freezer
):
    second = deepcopy(schedule)
    second["queue"] = "2.1"
    with patch(FETCH, return_value=[schedule, second]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        other = second_entry(hass)
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        assert fetch.call_count == 1
        first_coordinator = hass.data[DOMAIN][entry.entry_id]
        other_coordinator = hass.data[DOMAIN][other.entry_id]
        source = first_coordinator.source
        assert source is other_coordinator.source
        assert source.config_entry is None
        assert source.users == 2
        assert first_coordinator.data["queue"] == "2.2"
        assert other_coordinator.data["queue"] == "2.1"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert source.users == 1
        boundary = datetime(2026, 10, 7, 9, tzinfo=UTC) + timedelta(
            seconds=SCAN_INTERVAL_SECONDS + 5
        )
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert fetch.call_count == 2
        assert await hass.config_entries.async_unload(other.entry_id)
        await hass.async_block_till_done()
        assert not hass.data[DOMAIN][DATA_AREAS]
        later = boundary + timedelta(minutes=5)
        freezer.move_to(later)
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()
        assert fetch.call_count == 2


async def test_concurrent_first_setups_are_coalesced(hass, entry, schedule):
    other = second_entry(hass)
    second = {**schedule, "queue": "2.1"}
    started = asyncio.Event()
    finish = asyncio.Event()

    async def read(area):
        started.set()
        await finish.wait()
        return [schedule, second]

    with patch(FETCH, side_effect=read) as fetch:
        first_task = asyncio.create_task(
            hass.config_entries.async_setup(entry.entry_id)
        )
        await started.wait()
        # Loading the integration schedules all pre-existing entries itself.
        await asyncio.sleep(0)
        finish.set()
        assert await first_task
        await hass.async_block_till_done()
        assert other.state.value == "loaded"
    assert fetch.call_count == 1
    assert (
        hass.data[DOMAIN][entry.entry_id].source
        is hass.data[DOMAIN][other.entry_id].source
    )


async def test_different_areas_have_separate_sources(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        other = second_entry(hass, "kyivska-oblast")
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
    assert fetch.call_count == 2
    assert {call.args[0] for call in fetch.call_args_list} == {"kyiv", "kyivska-oblast"}
    assert len(hass.data[DOMAIN][DATA_AREAS]) == 2


async def test_initial_failure_discards_source_and_retries(hass, entry, schedule):
    with patch(FETCH, side_effect=AlertsEnergyApiError("offline")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert not hass.data[DOMAIN][DATA_AREAS]
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.data[DOMAIN][DATA_AREAS]) == 1


async def test_cancelled_acquire_cleans_clock_and_source(hass):
    started = asyncio.Event()

    async def read(area):
        started.set()
        await asyncio.Event().wait()

    api = AlertsEnergyApi(async_get_clientsession(hass))
    with patch(FETCH, side_effect=read):
        task = asyncio.create_task(async_acquire_area(hass, api, "kyiv"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not hass.data[DOMAIN][DATA_AREAS]


async def test_disable_polling_and_enabled_subscriber(hass, entry, schedule, freezer):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        boundary = datetime(2026, 10, 7, 9, 1, 5, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert fetch.call_count == 1
        other = second_entry(hass)
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        boundary += timedelta(seconds=65)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert fetch.call_count == 2
        assert await hass.config_entries.async_unload(other.entry_id)
        await hass.async_block_till_done()
        boundary += timedelta(seconds=SCAN_INTERVAL_SECONDS + 5)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert fetch.call_count == 2
