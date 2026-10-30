"""Polling options, shared scheduling, live changes and listener cleanup."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.alerts_energy_outages.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_OPERATOR,
    DOMAIN,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)


async def advance(hass, freezer, seconds):
    when = dt_util.utcnow() + timedelta(seconds=seconds)
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def save_interval(hass, entry, minutes):
    form = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {CONF_SCAN_INTERVAL: minutes}
    )
    await hass.async_block_till_done()
    return result


@pytest.mark.parametrize("options,expected", [({}, 15), ({CONF_SCAN_INTERVAL: 30}, 30)])
async def test_options_form_uses_default_or_saved_interval(
    hass, entry, options, expected
):
    hass.config_entries.async_update_entry(entry, options=options)
    form = await hass.config_entries.options.async_init(entry.entry_id)
    assert form["type"] == FlowResultType.FORM
    assert form["step_id"] == "init"
    field = next(iter(form["data_schema"].schema))
    assert field.default() == expected
    hass.config_entries.options.async_abort(form["flow_id"])
    assert entry.options == options


@pytest.mark.parametrize("minutes", [15, 30.0, 1440])
async def test_options_preserve_data_and_other_options(hass, entry, minutes):
    hass.config_entries.async_update_entry(entry, options={"retained": True})
    previous = dict(entry.data)
    identity = entry.unique_id
    result = await save_interval(hass, entry, minutes)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options == {"retained": True, CONF_SCAN_INTERVAL: int(minutes)}
    assert type(entry.options[CONF_SCAN_INTERVAL]) is int
    assert entry.data == previous
    assert entry.unique_id == identity


@pytest.mark.parametrize("minutes", [0, 1, 14, -1, 1441, "five", None])
async def test_invalid_interval_does_not_change_options(hass, entry, minutes):
    form = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            form["flow_id"], {CONF_SCAN_INTERVAL: minutes}
        )
    assert not entry.options
    hass.config_entries.options.async_abort(form["flow_id"])


async def test_fractional_interval_shows_translated_error(hass, entry):
    result = await save_interval(hass, entry, 15.5)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_SCAN_INTERVAL: "invalid_scan_interval"}
    assert not entry.options
    hass.config_entries.options.async_abort(result["flow_id"])


async def test_live_options_reschedule_without_reload_and_survive_reload(
    hass, entry, schedule, freezer
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        source = coordinator.source
        listeners = len(entry.update_listeners)
        assert source.update_interval == timedelta(minutes=15)
        await save_interval(hass, entry, 15)
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
        assert source.update_interval == timedelta(minutes=15)
        assert fetch.call_count == 1
        await advance(hass, freezer, 14 * 60)
        assert fetch.call_count == 1
        await advance(hass, freezer, 65)
        assert fetch.call_count == 2
        await save_interval(hass, entry, 20)
        await advance(hass, freezer, 6 * 60)
        assert fetch.call_count == 2
        await advance(hass, freezer, 14 * 60 + 5)
        assert fetch.call_count == 3
        assert len(entry.update_listeners) == listeners
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        reloaded = hass.data[DOMAIN][entry.entry_id].source
        assert reloaded is not source
        assert reloaded.update_interval == timedelta(minutes=20)
        assert len(entry.update_listeners) == listeners
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        with patch.object(reloaded, "async_update_polling_schedule") as reschedule:
            hass.config_entries.async_update_entry(
                entry, options={CONF_SCAN_INTERVAL: 1}
            )
            await hass.async_block_till_done()
        reschedule.assert_not_called()


async def test_shared_interval_tracks_enabled_entries_and_unload(hass, entry, schedule):
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 20})
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other queue",
        unique_id=f"{DEFAULT_OPERATOR}_2.1",
        minor_version=2,
        data={"operator": DEFAULT_OPERATOR, "queue": "2.1"},
        options={CONF_SCAN_INTERVAL: 15},
    )
    row = deepcopy(schedule)
    row["queue"] = "2.1"
    with patch(FETCH, return_value=[schedule, row]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        other.add_to_hass(hass)
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        source = hass.data[DOMAIN][entry.entry_id].source
        assert source is hass.data[DOMAIN][other.entry_id].source
        assert source.update_interval == timedelta(minutes=15)
        assert fetch.call_count == 1
        hass.config_entries.async_update_entry(other, pref_disable_polling=True)
        await hass.async_block_till_done()
        assert source.update_interval == timedelta(minutes=20)
        await save_interval(hass, other, 15)
        assert source.update_interval == timedelta(minutes=20)
        hass.config_entries.async_update_entry(other, pref_disable_polling=False)
        await hass.async_block_till_done()
        assert source.update_interval == timedelta(minutes=15)
        assert await hass.config_entries.async_unload(other.entry_id)
        await hass.async_block_till_done()
        assert source.update_interval == timedelta(minutes=20)
        assert source.users == 1


async def test_disabled_polling_stays_stopped_and_clock_still_runs(
    hass, entry, schedule, freezer
):
    hass.config_entries.async_update_entry(
        entry, options={CONF_SCAN_INTERVAL: 60}, pref_disable_polling=True
    )
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.last_update_success
        await save_interval(hass, entry, 15)
        with patch.object(coordinator, "async_update_listeners") as clock:
            await advance(hass, freezer, 30 * 60)
        assert clock.called
        assert fetch.call_count == 1
        hass.config_entries.async_update_entry(entry, pref_disable_polling=False)
        await hass.async_block_till_done()
        assert coordinator.source.update_interval == timedelta(minutes=15)
        await advance(hass, freezer, 15 * 60 + 5)
        assert fetch.call_count == 2


async def test_regions_keep_independent_polling_options(hass, entry, schedule):
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 15})
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        other = MockConfigEntry(
            domain=DOMAIN,
            title="Other region",
            unique_id=f"kyivska-oblast_{DEFAULT_OPERATOR}_2.2",
            minor_version=2,
            data={
                "area": "kyivska-oblast",
                "operator": DEFAULT_OPERATOR,
                "queue": "2.2",
            },
            options={CONF_SCAN_INTERVAL: 30},
        )
        other.add_to_hass(hass)
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        source = hass.data[DOMAIN][entry.entry_id].source
        other_source = hass.data[DOMAIN][other.entry_id].source
        assert source is not other_source
        assert source.update_interval == timedelta(minutes=15)
        assert other_source.update_interval == timedelta(minutes=30)
        await save_interval(hass, entry, 60)
        assert source.update_interval == timedelta(minutes=60)
        assert other_source.update_interval == timedelta(minutes=30)
        assert fetch.call_count == 2
