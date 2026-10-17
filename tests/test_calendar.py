"""Calendar coverage, actual HA API, clock transitions and registry lifecycle."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.calendar import calendar_periods
from custom_components.alerts_energy_outages.const import CONF_SCAN_INTERVAL, DOMAIN

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)
RANGE_START = datetime(2026, 10, 6, 21, tzinfo=UTC)
RANGE_END = datetime(2026, 10, 8, 21, tzinfo=UTC)


def calendar_entity(hass, entry):
    entity_id = next(
        item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == "calendar"
    )
    return hass.data["calendar"].get_entity(entity_id)


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id], calendar_entity(hass, entry)


def test_cross_midnight_merges_and_marks_coverage_edges(schedule):
    schedule["today"] = [1] + [0] * 22 + [1]
    schedule["tomorrow"] = [1] + [0] * 22 + [1]
    periods = calendar_periods(schedule)
    assert len(periods) == 3
    assert not periods[0].start_known
    assert periods[0].end_known
    assert periods[1].start == datetime(2026, 10, 7, 20, tzinfo=UTC)
    assert periods[1].end == datetime(2026, 10, 7, 22, tzinfo=UTC)
    assert periods[1].start_known and periods[1].end_known
    assert periods[2].start_known
    assert not periods[2].end_known


@pytest.mark.parametrize("tomorrow_published", [True, False])
def test_midnight_end_depends_on_next_day_coverage(schedule, tomorrow_published):
    schedule["today"] = [0] * 23 + [1]
    schedule["tomorrow"] = [0] * 24 if tomorrow_published else []
    period = calendar_periods(schedule)[0]
    assert period.end_known is tomorrow_published


@pytest.mark.parametrize("today_published", [True, False])
def test_tomorrow_midnight_start_depends_on_previous_coverage(
    schedule, today_published
):
    schedule["today"] = [0] * 24 if today_published else []
    schedule["tomorrow"] = [1] + [0] * 23
    period = calendar_periods(schedule)[0]
    assert period.start_known is today_published


@pytest.mark.parametrize("day", ["today", "tomorrow"])
@pytest.mark.parametrize("status", ["unpublished", "invalid", "stale", "emergency"])
def test_each_day_is_independent(schedule, day, status):
    schedule["today"] = schedule["tomorrow"] = [0] * 12 + [1] + [0] * 11
    schedule[day] = schedule[day].copy()
    if status == "unpublished":
        schedule[day] = []
    elif status == "invalid":
        schedule[day][0] = True
    elif status == "stale":
        schedule[f"{day}Date"] = "2026-10-06"
    else:
        schedule[f"{day}Status"] = "EmergencyShutdowns"
    periods = calendar_periods(schedule)
    assert len(periods) == 1
    expected_day = 8 if day == "today" else 7
    assert periods[0].start == datetime(2026, 10, expected_day, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "utc_start", "duration"),
    [
        ("2026-10-25", datetime(2026, 10, 25, 0, tzinfo=UTC), 120),
        ("2026-03-29", None, 0),
    ],
)
def test_dst_reuses_real_utc_timeline(schedule, freezer, day, utc_start, duration):
    from datetime import date

    from custom_components.alerts_energy_outages.forecast import utc_midnight

    freezer.move_to(utc_midnight(date.fromisoformat(day)) + timedelta(minutes=10))
    schedule.update(todayDate=day, today=[0] * 24, tomorrow=[])
    schedule["today"][3] = 1
    periods = calendar_periods(schedule)
    if utc_start is None:
        assert periods == []
    else:
        assert len(periods) == 1
        assert periods[0].start == utc_start
        assert (periods[0].end - periods[0].start).total_seconds() / 60 == duration


async def test_calendar_range_overlap_uids_and_no_extra_fetch(hass, entry, schedule):
    schedule["tomorrow"][18] = 3
    with patch(FETCH, return_value=[schedule]) as fetch:
        _, calendar = await setup(hass, entry)
        assert calendar.supported_features == 0
        assert hass.states.get(calendar.entity_id).state == "on"
        assert calendar.event.start == datetime(2026, 10, 7, 9, tzinfo=UTC)
        events = await calendar.async_get_events(hass, RANGE_START, RANGE_END)
        assert len(events) == 2
        assert events[0].start == datetime(2026, 10, 7, 9, tzinfo=UTC)
        assert events[0].end == datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        assert events[1].start == datetime(2026, 10, 8, 15, 30, tzinfo=UTC)
        assert not events[0].all_day
        assert events[0].uid != events[1].uid
        repeated = await calendar.async_get_events(hass, RANGE_START, RANGE_END)
        assert repeated == events
        # Return the complete event when a query only intersects its middle.
        overlapping = await calendar.async_get_events(
            hass,
            events[0].start + timedelta(minutes=5),
            events[0].end - timedelta(minutes=5),
        )
        assert overlapping == [events[0]]
        assert await calendar.async_get_events(hass, RANGE_START, events[0].start) == []
        assert (
            await calendar.async_get_events(hass, events[0].end, events[1].start) == []
        )
        assert (
            await calendar.async_get_events(hass, events[0].start, events[0].start)
            == []
        )
        assert fetch.call_count == 1


async def test_unknown_end_is_explicit_and_forecast_stays_unknown(
    hass, entry, schedule, freezer
):
    freezer.move_to(datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    schedule.update(today=[0] * 23 + [1], tomorrow=[])
    with patch(FETCH, return_value=[schedule]):
        _, calendar = await setup(hass, entry)
        event = calendar.event
        assert event.end == datetime(2026, 10, 7, 21, tzinfo=UTC)
        assert "not a confirmed restoration time" in event.description
        assert calendar.extra_state_attributes["event_end_known"] is False
        restoration_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.unique_id}_expected_restoration"
        )
        assert hass.states.get(restoration_id).state == "unknown"


async def test_failure_recovery_and_schedule_replacement(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, calendar = await setup(hass, entry)
        previous = await calendar.async_get_events(hass, RANGE_START, RANGE_END)
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        assert hass.states.get(calendar.entity_id).state == "on"
        assert hass.states.get(calendar.entity_id).attributes["data_is_cached"]
        assert await calendar.async_get_events(hass, RANGE_START, RANGE_END) == previous
        fetch.side_effect = None
        changed = deepcopy(schedule)
        changed["today"] = [0] * 24
        changed["tomorrow"][16] = 1
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        assert hass.states.get(calendar.entity_id).state == "off"
        events = await calendar.async_get_events(hass, RANGE_START, RANGE_END)
        assert len(events) == 1
        assert events[0].start == datetime(2026, 10, 8, 13, tzinfo=UTC)


async def test_zero_day_is_available_and_tomorrow_can_stand_alone(
    hass, entry, schedule
):
    schedule.update(today=[], tomorrow=[0] * 24, tomorrowStatus="NoShutdowns")
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, calendar = await setup(hass, entry)
        assert calendar.available
        assert calendar.event is None
        assert await calendar.async_get_events(hass, RANGE_START, RANGE_END) == []
        assert calendar.extra_state_attributes["today_schedule_status"] == "unpublished"
        fetch.return_value = []
        await coordinator.async_refresh()
        assert not calendar.available
        with pytest.raises(HomeAssistantError):
            await calendar.async_get_events(hass, RANGE_START, RANGE_END)


async def test_localized_descriptions_and_clock_only_transitions(
    hass, entry, schedule, freezer
):
    hass.config.language = "uk"
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 1440})
    schedule["today"][0] = 1
    with patch(FETCH, return_value=[schedule]) as fetch:
        _, calendar = await setup(hass, entry)
        assert "Планове відключення" in calendar.event.summary
        events = await calendar.async_get_events(hass, RANGE_START, RANGE_END)
        assert "відключення могло початися раніше" in events[0].description
        boundary = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert calendar.event is None
        assert hass.states.get(calendar.entity_id).state == "off"
        assert fetch.call_count == 1
        boundary = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert hass.states.get(calendar.entity_id).state == "unavailable"


async def test_actual_calendar_http_and_service(hass, entry, schedule, hass_client):
    with patch(FETCH, return_value=[schedule]) as fetch:
        _, calendar = await setup(hass, entry)
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{calendar.entity_id}",
            params={"start": RANGE_START.isoformat(), "end": RANGE_END.isoformat()},
        )
        assert response.status == 200
        events = await response.json()
        assert len(events) == 1
        assert datetime.fromisoformat(events[0]["start"]["dateTime"]) == datetime(
            2026, 10, 7, 9, tzinfo=UTC
        )
        result = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": calendar.entity_id,
                "start_date_time": RANGE_START.isoformat(),
                "end_date_time": RANGE_END.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        assert len(result[calendar.entity_id]["events"]) == 1
        assert fetch.call_count == 1


async def test_actual_calendar_start_trigger(hass, entry, schedule, freezer):
    schedule["today"][12] = 3
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 1440})
    calls = async_mock_service(hass, "test", "calendar_started")
    with patch(FETCH, return_value=[schedule]) as fetch:
        _, calendar = await setup(hass, entry)
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "alias": "Calendar start",
                        "trigger": {
                            "platform": "calendar",
                            "entity_id": calendar.entity_id,
                            "event": "start",
                        },
                        "action": {"service": "test.calendar_started"},
                    }
                ]
            },
        )
        await hass.async_start()
        await hass.async_block_till_done()
        for minute in (0, 15, 30):
            boundary = datetime(2026, 10, 7, 9, minute, 1, tzinfo=UTC)
            freezer.move_to(boundary)
            hass.loop._scheduled.sort(key=lambda handle: handle.when())
            async_fire_time_changed(hass, boundary)
            await hass.async_block_till_done()
        assert len(calls) == 1
        assert fetch.call_count == 1
        await hass.services.async_call(
            "automation",
            "turn_off",
            {"entity_id": "automation.calendar_start"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_reload_keeps_calendar_and_device_identity(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]):
        _, calendar = await setup(hass, entry)
        registry = er.async_get(hass)
        original = registry.async_get(calendar.entity_id)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        reloaded = calendar_entity(hass, entry)
        assert reloaded.entity_id == calendar.entity_id
        assert registry.async_get(reloaded.entity_id).device_id == original.device_id
