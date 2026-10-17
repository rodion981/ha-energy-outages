"""Conditional intervals: complete code matrix and recorded public examples."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.alerts_energy_outages.const import DOMAIN
from custom_components.alerts_energy_outages.coordinator import (
    outage_periods,
    schedule_day_status,
)
from custom_components.alerts_energy_outages.forecast import schedule_forecast
from custom_components.alerts_energy_outages.schedule import normalize_day

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)
EXAMPLES = json.loads(Path("tests/fixtures/possible_outages.json").read_text())[
    "examples"
]


@pytest.mark.parametrize(("planned", "possible"), list(product(range(4), repeat=2)))
def test_all_half_hour_unions(planned, possible):
    schedule = normalize_day(
        {"today": [planned] + [0] * 23, "todayPossible": [possible] + [0] * 23}, "today"
    )
    expected_first = planned in (1, 2) or possible in (1, 2)
    expected_second = planned in (1, 3) or possible in (1, 3)
    actual = {
        slot
        for start, end in outage_periods(schedule.combined)
        for slot in range(start, end)
    }
    assert actual == ({0} if expected_first else set()) | (
        {1} if expected_second else set()
    )
    assert schedule.planned[0] == planned
    assert schedule.possible[0] == possible


@pytest.mark.parametrize(
    "possible",
    [
        None,
        False,
        "",
        {},
        [0] * 23,
        [0] * 25,
        [True] * 24,
        [0.0] * 24,
        ["0"] * 24,
        [-1] * 24,
        [8] * 24,
    ],
)
def test_invalid_possible_is_not_empty(schedule, possible):
    schedule["todayPossible"] = possible
    with pytest.raises(ValueError):
        normalize_day(schedule, "today")
    assert schedule_day_status(schedule, "today") == "invalid"


@pytest.mark.parametrize("possible", ["absent", [], [0] * 24])
def test_absent_empty_zero_possible_are_equivalent(schedule, possible):
    if possible != "absent":
        schedule["todayPossible"] = possible
    assert normalize_day(schedule, "today").combined == schedule["today"]
    assert schedule_day_status(schedule, "today") == "published"


@pytest.mark.parametrize("field", ["today", "todayPossible"])
def test_emergency_code_requires_current_date(schedule, field):
    schedule[field] = [9] + [0] * 23
    assert schedule_day_status(schedule, "today") == "emergency"
    schedule["todayDate"] = "2026-10-06"
    assert schedule_day_status(schedule, "today") != "emergency"
    assert schedule_day_status(schedule, "today") != "published"


def test_possible_cannot_complete_a_missing_main_schedule(schedule):
    schedule.update(today=[], todayPossible=[1] * 24)
    assert schedule_day_status(schedule, "today") == "unpublished"


def test_no_shutdowns_consistency_matches_source_planner(schedule):
    schedule.update(
        today=[0] * 24, todayPossible=[2] + [0] * 23, todayStatus="NoShutdowns"
    )
    assert schedule_day_status(schedule, "today") == "published"
    assert normalize_day(schedule, "today").outage_type == "possible"
    schedule["today"][0] = 1
    assert schedule_day_status(schedule, "today") == "invalid"


def test_overlap_has_planned_precedence_but_preserves_both_arrays(schedule):
    schedule["todayPossible"] = schedule["today"].copy()
    normalized = normalize_day(schedule, "today")
    assert normalized.combined == schedule["today"]
    assert normalized.outage_type == "planned"
    assert normalized.planned == normalized.possible


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example["area"])
async def test_recorded_examples_across_every_platform(
    hass, entry, schedule, freezer, example
):
    freezer.move_to(datetime(2026, 10, 17, 6, tzinfo=UTC))
    data = deepcopy(schedule)
    data.update(
        today=[0] * 24,
        tomorrow=[0] * 24,
        todayDate="2026-10-17",
        tomorrowDate="2026-10-18",
        initiator=example["operator"],
        queue=example["queue"],
    )
    day = example["day"]
    data[day] = example["planned"]
    data[f"{day}Possible"] = example["possible"]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "area": example["area"],
            "operator": example["operator"],
            "queue": example["queue"],
        },
    )
    with patch(FETCH, return_value=[data]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = {
            item.unique_id.removeprefix(entry.unique_id + "_"): item.entity_id
            for item in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        }
        state = hass.states.get(ids[day])
        expected_type = (
            "mixed" if example["area"] == "mikolayivska-oblast" else "possible"
        )
        assert state.attributes["hours"] == example["planned"]
        assert state.attributes["possible_hours"] == example["possible"]
        assert state.attributes["periods"] == example["expected_periods"]
        assert state.attributes["outage_type"] == expected_type
        assert state.attributes["possible_periods"]
        assert "possible" in state.state.lower()
        restoration = hass.states.get(ids["expected_restoration"])
        assert restoration.state not in {"unknown", "unavailable"}
        assert restoration.attributes["outage_type"] == expected_type
        binary = hass.states.get(ids["outage_now"])
        expected_on = example["area"] == "kharkivska-oblast"
        assert (binary.state == "on") is expected_on
        assert binary.attributes["outage_type"] == (
            "possible" if expected_on else "none"
        )
        calendar = hass.data["calendar"].get_entity(ids["outage_calendar"])
        events = await calendar.async_get_events(
            hass,
            datetime(2026, 10, 16, 21, tzinfo=UTC),
            datetime(2026, 10, 18, 21, tzinfo=UTC),
        )
        assert len(events) == len(example["expected_periods"])
        assert "possible" in calendar.event.summary.lower()
        assert "not guaranteed" in calendar.event.description
        assert fetch.call_count == 1


@pytest.mark.parametrize(
    ("date", "utc_start", "minutes"),
    [
        ("2026-10-25", datetime(2026, 10, 25, 0, tzinfo=UTC), 120),
        ("2026-03-29", datetime(2026, 3, 28, 23, tzinfo=UTC), 180),
    ],
)
def test_possible_only_dst_uses_real_duration(
    schedule, freezer, date, utc_start, minutes
):
    freezer.move_to(utc_start)
    schedule.update(today=[0] * 24, tomorrow=[], todayDate=date, todayPossible=[0] * 24)
    if date == "2026-10-25":
        schedule["todayPossible"][3] = 1
    else:
        schedule["todayPossible"][1:5] = [1] * 4
    forecast = schedule_forecast(schedule, utc_start + timedelta(minutes=10))
    assert forecast.selected.outage_type == "possible"
    assert forecast.selected.duration_minutes == minutes


def test_mixed_midnight_and_unknown_horizon(schedule):
    schedule.update(
        today=[0] * 23 + [1], tomorrow=[0] * 24, tomorrowPossible=[1] + [0] * 23
    )
    forecast = schedule_forecast(schedule, datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    assert forecast.selected.outage_type == "mixed"
    assert forecast.selected.duration_minutes == 120
    schedule["tomorrowPossible"] = [1] * 24
    forecast = schedule_forecast(schedule, datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    assert forecast.selected.end is None
    assert forecast.selected.duration_minutes is None


async def test_possible_schedule_state_limit_keeps_complete_attributes(
    hass, entry, schedule
):
    schedule.update(today=[0] * 24, todayPossible=[2] * 24)
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.unique_id}_today"
        )
        state = hass.states.get(entity)
        assert len(state.state) <= 255
        assert state.state.startswith("Possible:")
        assert (
            len(state.attributes["periods"])
            == len(state.attributes["possible_periods"])
            == 24
        )


@pytest.mark.parametrize(
    ("possible", "status"), [(None, "invalid"), ([9] + [0] * 23, "emergency")]
)
async def test_unusable_possible_data_is_not_a_zero_outage(
    hass, entry, schedule, possible, status
):
    schedule.update(today=[0] * 24, todayPossible=[0] * 12 + [1] + [0] * 11)
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)

        def sensor(key):
            return registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.unique_id}_{key}"
            )

        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.return_value = [{**schedule, "todayPossible": possible}]
        await coordinator.async_refresh()
        assert hass.states.get(sensor("today")).state == "unavailable"
        assert hass.states.get(sensor("expected_restoration")).state == "unavailable"
        assert hass.states.get(sensor("data_status")).state == status
        binary_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.unique_id}_outage_now"
        )
        assert hass.states.get(binary_id).state == "unavailable"
        assert hass.data["binary_sensor"].get_entity(binary_id).is_on is None
        assert (
            hass.data["binary_sensor"]
            .get_entity(binary_id)
            .extra_state_attributes["outage_type"]
            is None
        )
        fetch.return_value = [schedule]
        await coordinator.async_refresh()
        assert hass.states.get(binary_id).state == "on"
        assert hass.states.get(binary_id).attributes["outage_type"] == "possible"
