"""Use already dated tomorrow data after Kyiv midnight without another request."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alerts_energy_outages.api import (
    AlertsEnergyApiError,
    async_get_api,
)
from custom_components.alerts_energy_outages.const import API_URL, DOMAIN
from custom_components.alerts_energy_outages.schedule import align_schedule_dates

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)


def entities(hass, entry):
    identity = entry.data.get("entity_unique_id") or entry.unique_id or entry.entry_id
    return {
        item.unique_id.removeprefix(identity + "_"): item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


@pytest.mark.parametrize("offline", [False, True])
async def test_published_tomorrow_remains_usable_at_midnight(
    hass, entry, schedule, freezer, offline
):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    schedule.update(
        today=[0] * 23 + [1],
        tomorrow=[2] + [0] * 11 + [2] + [0] * 11,
        tomorrowPossible=[0] * 14 + [3] + [0] * 9,
        today_checked_at="2026-10-07T08:50:00Z",
        tomorrow_checked_at="2026-10-07T08:55:00Z",
        today_announcements=[],
    )
    original = deepcopy(schedule)
    freezer.move_to(datetime(2026, 10, 7, 20, 59, tzinfo=UTC))
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        receipt = coordinator.last_successful_update
        event_before = hass.states.get(ids["schedule_changed"]).state
        if offline:
            fetch.side_effect = AlertsEnergyApiError("offline")
            await coordinator.async_refresh()
        calls = fetch.call_count
        midnight = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(midnight)
        async_fire_time_changed(hass, midnight)
        await hass.async_block_till_done()
        today = hass.states.get(ids["today"])
        assert (
            today.state == "Planned and possible: 00:00–00:30; 12:00–12:30; 14:30–15:00"
        )
        assert today.attributes["date"] == "2026-10-08"
        assert today.attributes["data_is_cached"] is offline
        assert hass.states.get(ids["outage_now"]).state == "on"
        assert (
            hass.states.get(ids["expected_restoration"]).state
            == "2026-10-07T21:30:00+00:00"
        )
        assert hass.states.get(ids["next_outage"]).state == "2026-10-08T09:00:00+00:00"
        assert hass.states.get(ids["outage_duration"]).state == "unknown"
        assert hass.states.get(ids["outage_calendar"]).state == "on"
        assert hass.states.get(ids["tomorrow"]).state == "unavailable"
        assert hass.states.get(ids["data_status"]).state == (
            "connection_error" if offline else "published"
        )
        assert (
            hass.states.get(ids["today_checked_at"]).state
            == "2026-10-07T08:55:00+00:00"
        )
        assert hass.states.get(ids["tomorrow_checked_at"]).state == "unknown"
        assert hass.states.get(ids["emergency_notices"]).state == "unknown"
        assert hass.states.get(ids["schedule_changed"]).state == event_before
        assert coordinator.last_successful_update == receipt
        assert schedule == original
        assert fetch.call_count == calls


@pytest.mark.parametrize(
    ("original_date", "next_date", "midnight"),
    [
        ("2026-03-28", "2026-03-29", "2026-03-28T22:00:00+00:00"),
        ("2026-03-29", "2026-03-30", "2026-03-29T21:00:00+00:00"),
        ("2026-10-24", "2026-10-25", "2026-10-24T21:00:00+00:00"),
        ("2026-10-25", "2026-10-26", "2026-10-25T22:00:00+00:00"),
    ],
)
def test_alignment_uses_kyiv_dates_across_dst(
    schedule, original_date, next_date, midnight
):
    schedule.update(todayDate=original_date, tomorrowDate=next_date)
    view = align_schedule_dates(schedule, datetime.fromisoformat(midnight))
    assert view["todayDate"] == next_date
    assert view["today"] == schedule["tomorrow"]
    assert schedule["todayDate"] == original_date


def test_alignment_does_not_override_authoritative_day_or_invent_dates(schedule):
    schedule.update(tomorrowDate=schedule["todayDate"], today=None)
    original = deepcopy(schedule)
    assert (
        align_schedule_dates(schedule, datetime(2026, 10, 7, 9, tzinfo=UTC)) == original
    )
    schedule.update(todayDate="invalid", tomorrowDate=None)
    assert align_schedule_dates(schedule, datetime(2026, 10, 8, tzinfo=UTC)) == schedule


def test_alignment_moves_optional_fields_without_inheriting_yesterday(schedule):
    schedule.update(
        todayPossible=[1] * 24,
        today_checked_at="2026-10-07T08:00:00Z",
        today_announcements=[{"kind": "Emergency", "state": "active"}],
        today_published_schedule={"hours": [1] * 24},
        today_date="2026-10-07",
        tomorrow_date="2026-10-08",
        tomorrow_status="ScheduleApplies",
        tomorrow_possible=[],
    )
    view = align_schedule_dates(schedule, datetime(2026, 10, 7, 21, tzinfo=UTC))
    assert view["today_date"] == "2026-10-08"
    assert view["today_status"] == "ScheduleApplies"
    assert view["today_possible"] == []
    for field in (
        "todayPossible",
        "today_checked_at",
        "today_announcements",
        "today_published_schedule",
    ):
        assert field not in view
    assert schedule["today_announcements"]


@pytest.mark.parametrize(
    ("status", "hours", "possible", "expected"),
    [
        ("EmergencyShutdowns", [], [], "emergency"),
        ("ScheduleApplies", [0] * 24, [9] + [0] * 23, "emergency"),
        ("ScheduleApplies", None, [], "unpublished"),
        ("ScheduleApplies", [0] * 24, None, "invalid"),
        ("WaitingForSchedule", [0] * 24, [], "unpublished"),
        ("NoShutdowns", [1] * 24, [], "invalid"),
    ],
)
async def test_rollover_preserves_unusable_and_emergency_statuses(
    hass, entry, schedule, freezer, status, hours, possible, expected
):
    schedule.update(tomorrowStatus=status, tomorrow=hours, tomorrowPossible=possible)
    freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["today"]).state == "unavailable"
    assert hass.states.get(ids["data_status"]).state == expected
    assert hass.states.get(ids["outage_now"]).state == "unavailable"


async def test_restart_from_persisted_cache_after_midnight(
    hass, hass_storage, entry, schedule, aioclient_mock, freezer
):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    aioclient_mock.get(API_URL, json=[schedule])
    api = await async_get_api(hass)
    await api.async_get_schedules()
    hass.data[DOMAIN].pop("_api")
    freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["today"]).state == "No outages"
    assert hass.states.get(ids["today"]).attributes["data_is_cached"]
    assert hass.states.get(ids["data_status"]).state == "connection_error"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entities(hass, entry) == ids
    assert hass.states.get(ids["today"]).state == "No outages"
    assert aioclient_mock.call_count == 1


async def test_rollover_expiry_and_new_response_do_not_reuse_old_day(
    hass, entry, schedule, freezer
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
        coordinator.source._handle_clock(datetime(2026, 10, 7, 21, tzinfo=UTC))
        assert hass.states.get(ids["today"]).state == "No outages"
        fetch.return_value = [{**schedule, "tomorrow": []}]
        await coordinator.async_refresh()
        assert hass.states.get(ids["today"]).state == "unavailable"
        fetch.return_value = [schedule]
        await coordinator.async_refresh()
        assert hass.states.get(ids["today"]).state == "No outages"
        boundary = datetime(2026, 10, 8, 21, tzinfo=UTC)
        freezer.move_to(boundary)
        coordinator.source._handle_clock(boundary)
        assert hass.states.get(ids["today"]).state == "unavailable"
