"""Source verification and scoped advisory messages in real HA entities."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alerts_energy_outages.api import (
    AlertsEnergyApiError,
    async_get_api,
)
from custom_components.alerts_energy_outages.const import API_URL, DOMAIN
from custom_components.alerts_energy_outages.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.alerts_energy_outages.source import (
    emergency_notices,
    source_checked_at,
    source_timestamp,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)
NOW = datetime(2026, 10, 7, 9, tzinfo=UTC)


def notice(**changes):
    return {
        "kind": "Emergency",
        "state": "active",
        "scope": "local",
        "published_at": "2026-10-07T08:45:00Z",
        "effective_at": "2026-10-07T08:50:00Z",
        "expires_at": "2026-10-07T09:07:00Z",
        **changes,
    }


def entities(hass, entry):
    identity = entry.data.get("entity_unique_id") or entry.unique_id or entry.entry_id
    return {
        item.unique_id.removeprefix(identity + "_"): item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        123,
        [],
        {},
        "",
        "bad",
        "2026-10-07T09:00:00",
        "2026-99-99T00:00:00Z",
        "0001-01-01T00:00:00+14:00",
    ],
)
def test_invalid_source_timestamp(value):
    assert source_timestamp(value) is None


def test_source_checks_are_typed_dated_and_independent(schedule):
    schedule.update(
        today_checked_at="2026-10-07T11:50:00+03:00", tomorrow_checked_at="bad"
    )
    assert source_checked_at(schedule, "today", NOW) == datetime(
        2026, 10, 7, 8, 50, tzinfo=UTC
    )
    assert source_checked_at(schedule, "tomorrow", NOW) is None
    schedule["todayDate"] = "2026-10-06"
    assert source_checked_at(schedule, "today", NOW) is None


@pytest.mark.parametrize(
    ("announcements", "warning"),
    [
        ([], False),
        ([notice()], True),
        ([notice(state="possible")], True),
        ([notice(state="cancelled")], False),
        ([notice(kind="GPV")], False),
        ([notice(scope="supplier")], True),
        ([notice(scope="regional")], True),
        ([notice(effective_at="2026-10-07T09:01:00Z")], False),
        ([notice(expires_at="2026-10-07T09:00:00Z")], False),
        ([notice(expires_at="2026-10-07T08:49:00Z")], None),
        ([notice(effective_at="bad")], None),
        ([notice(expires_at=None)], None),
        ([notice(scope="unknown")], None),
        ([notice(state="unknown")], None),
        ([notice(), notice(scope=None)], True),
        ([{}], None),
        ([False], None),
        (None, None),
        ({}, None),
    ],
)
def test_notice_validation(schedule, announcements, warning):
    schedule["today_announcements"] = announcements
    assert emergency_notices(schedule, NOW).warning is warning


def test_notice_missing_stale_and_optional_timing(schedule):
    assert emergency_notices(schedule, NOW).warning is None
    schedule["today_announcements"] = [
        {"kind": "Emergency", "scope": "local", "state": "active"}
    ]
    assert emergency_notices(schedule, NOW).warning is True
    assert emergency_notices(schedule, NOW).boundaries == ()
    schedule["todayDate"] = "2026-10-06"
    assert emergency_notices(schedule, NOW).warning is None


async def test_new_fields_through_client_without_altering_schedule(
    hass, entry, schedule, aioclient_mock
):
    row = deepcopy(schedule)
    for suffix in ("Date", "Status"):
        for day in ("today", "tomorrow"):
            row[f"{day}_{suffix.lower()}"] = row.pop(f"{day}{suffix}")
    row.update(
        today_announcements=[notice(private_extra="do not export")],
        today_checked_at="2026-10-07T08:50:00Z",
        tomorrow_checked_at="2026-10-07T08:55:00Z",
    )
    aioclient_mock.get(API_URL, json=[row])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entities(hass, entry)
    warning = hass.states.get(ids["emergency_notices"])
    assert warning.state == "on"
    assert warning.attributes["address_specific"] is False
    assert warning.attributes["announcements"][0]["scope"] == "local"
    assert "private_extra" not in str(warning.attributes)
    assert "outage_end" not in warning.attributes
    assert hass.states.get(ids["today_checked_at"]).state == "2026-10-07T08:50:00+00:00"
    assert (
        hass.states.get(ids["tomorrow_checked_at"]).state == "2026-10-07T08:55:00+00:00"
    )
    assert hass.states.get(ids["last_successful_update"]).state == NOW.isoformat()
    assert hass.states.get(ids["today"]).state == "12:00–12:30"
    assert hass.states.get(ids["data_status"]).state == "published"
    assert aioclient_mock.call_count == 1
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["days"]["today"]["checked_at"] == "2026-10-07T08:50:00+00:00"
    assert diagnostics["emergency_notices"]["warning"] is True
    assert "private_extra" not in str(diagnostics)


async def test_missing_optional_fields_unknown_and_empty_list_off(
    hass, entry, schedule
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        for key in ("emergency_notices", "today_checked_at", "tomorrow_checked_at"):
            assert hass.states.get(ids[key]).state == "unknown"
        fetch.return_value = [{**schedule, "today_announcements": []}]
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["emergency_notices"]).state == "off"


async def test_notice_start_expiry_during_cached_failure_without_polling(
    hass, entry, schedule, freezer
):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    schedule.update(
        today_announcements=[notice(effective_at="2026-10-07T09:03:00Z")],
        today_checked_at="2026-10-07T08:50:00Z",
    )
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert hass.states.get(ids["emergency_notices"]).state == "off"
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        for minute, expected in ((3, "on"), (7, "off")):
            now = NOW.replace(minute=minute)
            freezer.move_to(now)
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()
            state = hass.states.get(ids["emergency_notices"])
            assert state.state == expected
            assert state.attributes["data_is_cached"] is True
        assert coordinator.source._unsub_announcements is None
        assert fetch.call_count == 2
        assert (
            hass.states.get(ids["today_checked_at"]).state
            == "2026-10-07T08:50:00+00:00"
        )
        assert hass.states.get(ids["last_successful_update"]).state == NOW.isoformat()
        midnight = datetime(2026, 10, 7, 21, tzinfo=UTC)
        freezer.move_to(midnight)
        async_fire_time_changed(hass, midnight)
        await hass.async_block_till_done()
        assert hass.states.get(ids["emergency_notices"]).state == "unknown"
        assert hass.states.get(ids["today_checked_at"]).state == "unknown"


async def test_cancel_recovery_and_reload_preserve_identity(hass, entry, schedule):
    schedule["today_announcements"] = [notice()]
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        source = hass.data[DOMAIN][entry.entry_id].source
        assert source._unsub_announcements is not None
        fetch.return_value = [
            {**schedule, "today_announcements": [notice(state="cancelled")]}
        ]
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["emergency_notices"]).state == "off"
        assert source._unsub_announcements is None
        fetch.side_effect = AlertsEnergyApiError("offline")
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(ids["emergency_notices"]).state == "off"
        fetch.side_effect = None
        fetch.return_value = [schedule]
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entities(hass, entry) == ids
        assert hass.states.get(ids["emergency_notices"]).state == "on"
        assert source._unsub_announcements is None
        current = hass.data[DOMAIN][entry.entry_id].source
        assert current._unsub_announcements is not None
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert current._unsub_announcements is None


async def test_shared_timer_survives_first_entry_unload(hass, entry, schedule, freezer):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        unique_id="other_queue",
        data={"operator": schedule["initiator"], "queue": "2.1"},
        pref_disable_polling=True,
    )
    other.add_to_hass(hass)
    schedule["today_announcements"] = [notice()]
    with patch(FETCH, return_value=[schedule, {**schedule, "queue": "2.1"}]) as fetch:
        for current in (entry, other):
            if current.state.value != "loaded":
                assert await hass.config_entries.async_setup(current.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, other)
        source = hass.data[DOMAIN][entry.entry_id].source
        assert source is hass.data[DOMAIN][other.entry_id].source
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert source._unsub_announcements is not None
        expiry = NOW.replace(minute=7)
        freezer.move_to(expiry)
        async_fire_time_changed(hass, expiry)
        await hass.async_block_till_done()
        assert hass.states.get(ids["emergency_notices"]).state == "off"
        assert fetch.call_count == 1
        assert await hass.config_entries.async_unload(other.entry_id)
        assert source._unsub_announcements is None


async def test_notice_notification_automation_no_recovery_or_reload_repeat(
    hass, entry, schedule
):
    schedule["today_announcements"] = []
    calls = async_mock_service(hass, "test", "notify")
    with patch(FETCH, return_value=[schedule]) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ids = entities(hass, entry)
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "alias": "Emergency advisory",
                        "trigger": [
                            {
                                "platform": "state",
                                "entity_id": ids["emergency_notices"],
                                "from": "off",
                                "to": "on",
                            }
                        ],
                        "action": [{"service": "test.notify"}],
                    }
                ]
            },
        )
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.return_value = [{**schedule, "today_announcements": [notice()]}]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 1
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        fetch.side_effect = None
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert len(calls) == 1


async def test_shutdown_does_not_recreate_notice_timer(hass, entry, schedule):
    schedule["today_announcements"] = [notice()]
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        source = hass.data[DOMAIN][entry.entry_id].source
        assert await hass.config_entries.async_unload(entry.entry_id)
        source._schedule_announcement_boundary([schedule])
        assert source._unsub_announcements is None


async def test_persisted_notices_start_offline_and_expire_locally(
    hass, hass_storage, entry, schedule, aioclient_mock, freezer
):
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    schedule.update(
        today_announcements=[notice(expires_at="2026-10-07T09:25:00Z")],
        today_checked_at="2026-10-07T08:50:00Z",
    )
    aioclient_mock.get(API_URL, json=[schedule])
    api = await async_get_api(hass)
    await api.async_get_schedules()
    hass.data[DOMAIN].pop("_api")
    freezer.move_to(NOW.replace(minute=15, second=1))
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entities(hass, entry)
    state = hass.states.get(ids["emergency_notices"])
    assert state.state == "on"
    assert state.attributes["data_is_cached"] is True
    assert hass.states.get(ids["data_status"]).state == "connection_error"
    assert hass.states.get(ids["last_successful_update"]).state == NOW.isoformat()
    assert hass.states.get(ids["today_checked_at"]).state == "2026-10-07T08:50:00+00:00"
    expiry = NOW.replace(minute=25)
    freezer.move_to(expiry)
    async_fire_time_changed(hass, expiry)
    await hass.async_block_till_done()
    assert hass.states.get(ids["emergency_notices"]).state == "off"
    assert aioclient_mock.call_count == 1


async def test_notices_and_source_checks_do_not_require_published_hours(
    hass, entry, schedule
):
    schedule.update(
        today=[],
        todayStatus="EmergencyShutdowns",
        today_announcements=[notice()],
        today_checked_at="2026-10-07T08:50:00Z",
    )
    with patch(FETCH, return_value=[schedule]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = entities(hass, entry)
    assert hass.states.get(ids["today"]).state == "unavailable"
    assert hass.states.get(ids["emergency_notices"]).state == "on"
    assert hass.states.get(ids["today_checked_at"]).state == "2026-10-07T08:50:00+00:00"
