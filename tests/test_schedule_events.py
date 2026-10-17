"""Real event entities, comparison lifecycle and notification blueprint."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import CONF_SCAN_INTERVAL, DOMAIN
from custom_components.alerts_energy_outages.event import (
    AlertsEnergyScheduleChangeEvent,
    ScheduleChangeStoredData,
)

FETCH = (
    "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules"
)
BLUEPRINT = Path("blueprints/automation/schedule_changes.yaml")


def event_id(hass, entry):
    return next(
        item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == "event"
    )


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id], event_id(hass, entry)


async def test_changed_periods_both_days_are_one_event(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        assert hass.states.get(entity).state == "unknown"
        changed = deepcopy(schedule)
        changed["today"][12] = 3
        changed["tomorrow"][23] = 1
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(entity)
        assert state.attributes["event_type"] == "schedule_changed"
        assert state.attributes["queue"] == "2.2"
        assert state.attributes["changes"] == [
            {
                "date": "2026-10-07",
                "change_type": "changed",
                "before": [{"start": "12:00", "end": "12:30"}],
                "after": [{"start": "12:30", "end": "13:00"}],
                "added": [{"start": "12:30", "end": "13:00"}],
                "removed": [{"start": "12:00", "end": "12:30"}],
                "planned": [{"start": "12:30", "end": "13:00"}],
                "possible": [],
                "previous_planned": [{"start": "12:00", "end": "12:30"}],
                "previous_possible": [],
                "classification_changed": False,
            },
            {
                "date": "2026-10-08",
                "change_type": "changed",
                "before": [],
                "after": [{"start": "23:00", "end": "24:00"}],
                "added": [{"start": "23:00", "end": "24:00"}],
                "removed": [],
                "planned": [{"start": "23:00", "end": "24:00"}],
                "possible": [],
                "previous_planned": [],
                "previous_possible": [],
                "classification_changed": False,
            },
        ]
        # No extra request for history or each configured entity.
        assert fetch.call_count == 2


async def test_timestamp_clock_and_recovery_do_not_replay(
    hass, entry, schedule, freezer
):
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 1440})
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        changed = deepcopy(schedule)
        changed["today"] = [0] * 24
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        previous = hass.states.get(entity)
        changed["updated"] = "2026-10-07T09:10:00Z"
        await coordinator.async_refresh()
        fetch.side_effect = AlertsEnergyApiError("offline")
        await coordinator.async_refresh()
        fetch.side_effect = None
        await coordinator.async_refresh()
        boundary = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
        freezer.move_to(boundary)
        async_fire_time_changed(hass, boundary)
        await hass.async_block_till_done()
        assert hass.states.get(entity) == previous


@pytest.mark.parametrize("kind", ["missing", "invalid", "stale", "emergency"])
async def test_unconfirmed_data_is_not_cancellation(hass, entry, schedule, kind):
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        bad = deepcopy(schedule)
        if kind == "missing":
            bad["today"] = []
        elif kind == "invalid":
            bad["today"][0] = 9
        elif kind == "stale":
            bad["todayDate"] = "2026-10-06"
        else:
            bad["todayStatus"] = "EmergencyShutdowns"
        fetch.return_value = [bad]
        await coordinator.async_refresh()
        assert hass.states.get(entity).state == "unknown"
        fetch.return_value = [schedule]
        await coordinator.async_refresh()
        assert hass.states.get(entity).state == "unknown"
        changed = deepcopy(schedule)
        changed["today"] = [0] * 24
        changed["todayStatus"] = "NoShutdowns"
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        assert hass.states.get(entity).attributes["changes"][0]["removed"] == [
            {"start": "12:00", "end": "12:30"}
        ]


@pytest.mark.parametrize("hours", [[0] * 24, [1] + [0] * 23])
async def test_first_publication_after_setup(hass, entry, schedule, hours):
    initial = {**schedule, "tomorrow": []}
    with patch(FETCH, return_value=[initial]) as fetch:
        coordinator, entity = await setup(hass, entry)
        assert hass.states.get(entity).state == "unknown"
        fetch.return_value = [{**schedule, "tomorrow": hours}]
        await coordinator.async_refresh()
        change = hass.states.get(entity).attributes["changes"][0]
        assert change["date"] == "2026-10-08"
        assert change["change_type"] == "published"
        assert change["before"] is None
        assert change["removed"] == []


async def test_midnight_moves_tomorrow_to_today_without_event(
    hass, entry, schedule, freezer
):
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
        rolled = deepcopy(schedule)
        rolled.update(
            today=schedule["tomorrow"],
            todayDate="2026-10-08",
            tomorrow=[],
            tomorrowDate="2026-10-09",
        )
        fetch.return_value = [rolled]
        await coordinator.async_refresh()
        assert hass.states.get(entity).state == "unknown"
        rolled["tomorrow"] = [0] * 24
        await coordinator.async_refresh()
        assert hass.states.get(entity).attributes["changes"][0]["date"] == "2026-10-09"


@pytest.mark.parametrize(
    "restore_kind",
    [
        "valid",
        "different_queue",
        "invalid_hours",
        "new_valid",
        "new_invalid",
        "bad_type",
    ],
)
async def test_restore_deduplicates_temporarily_missing_day(
    hass, entry, schedule, restore_kind
):
    stored = ScheduleChangeStoredData(
        {
            "schedule_identity": ["kyiv", schedule["initiator"], "2.2"],
            "schedules": {"2026-10-08": schedule["tomorrow"]},
        }
    )
    if restore_kind == "different_queue":
        stored.data["schedule_identity"][-1] = "1.1"
    elif restore_kind == "invalid_hours":
        stored.data["schedules"]["2026-10-08"] = [True] * 24
    elif restore_kind == "new_valid":
        stored.data["schedules"]["2026-10-08"] = {
            "planned": schedule["tomorrow"],
            "possible": [0] * 24,
        }
    elif restore_kind == "new_invalid":
        stored.data["schedules"]["2026-10-08"] = {
            "planned": schedule["tomorrow"],
            "possible": None,
        }
    elif restore_kind == "bad_type":
        stored.data["schedules"]["2026-10-08"] = "invalid"
    with (
        patch(FETCH, return_value=[{**schedule, "tomorrow": []}]) as fetch,
        patch.object(
            AlertsEnergyScheduleChangeEvent,
            "async_get_last_extra_data",
            return_value=stored,
        ),
    ):
        coordinator, entity = await setup(hass, entry)
        fetch.return_value = [schedule]
        await coordinator.async_refresh()
        assert (hass.states.get(entity).state == "unknown") == (
            restore_kind in {"valid", "new_valid"}
        )


async def test_reload_is_quiet_and_identity_is_preserved(hass, entry, schedule):
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        changed = deepcopy(schedule)
        changed["today"][12] = 1
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        previous = hass.states.get(entity)
        fetch.return_value = [{**changed, "tomorrow": []}]
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert event_id(hass, entry) == entity
        state = hass.states.get(entity)
        assert state.state == previous.state
        assert state.attributes["changes"] == previous.attributes["changes"]
        fetch.return_value = [changed]
        await hass.data[DOMAIN][entry.entry_id].async_refresh()
        assert hass.states.get(entity) == state


async def test_possible_only_restore_and_classification_notifications(
    hass, entry, schedule, notification_blueprint
):
    schedule.update(today=[0] * 24, todayPossible=[0] * 16 + [1] + [0] * 7)
    calls = async_mock_service(hass, "test", "notify")
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "alias": "Conditional notifications",
                        "use_blueprint": {
                            "path": "alerts_energy_outages/schedule_changes.yaml",
                            "input": {
                                "schedule_event": entity,
                                "notification_actions": [
                                    {
                                        "service": "test.notify",
                                        "data": {
                                            "message": "{{ notification_message }}"
                                        },
                                    }
                                ],
                            },
                        },
                    }
                ]
            },
        )
        await hass.async_block_till_done()
        changed = deepcopy(schedule)
        changed["todayPossible"][16:18] = [0, 1]
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert "Можливі відключення: 17:00–18:00" in calls[0].data["message"]
        previous_state = hass.states.get(entity)
        fetch.return_value = [{**changed, "today": []}]
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity).state == previous_state.state
        assert len(calls) == 1
        # The same union becomes planned: notify once without fake additions/removals.
        confirmed = {
            **changed,
            "today": changed["todayPossible"].copy(),
            "todayPossible": [0] * 24,
        }
        fetch.return_value = [confirmed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 2
        change = hass.states.get(entity).attributes["changes"][0]
        assert change["classification_changed"] is True
        assert change["added"] == change["removed"] == []
        assert change["previous_possible"] == change["planned"]
        assert "Уточнено тип інтервалів" in calls[1].data["message"]
        assert "Планові відключення: 17:00–18:00" in calls[1].data["message"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_invalid_possible_does_not_cancel_event(hass, entry, schedule):
    schedule.update(today=[0] * 24, todayPossible=[0] * 12 + [1] + [0] * 11)
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        invalid = {**schedule, "todayPossible": None}
        fetch.return_value = [invalid]
        await coordinator.async_refresh()
        assert hass.states.get(entity).state == "unknown"
        fetch.return_value = [schedule]
        await coordinator.async_refresh()
        assert hass.states.get(entity).state == "unknown"
        fetch.return_value = [{**schedule, "todayPossible": []}]
        await coordinator.async_refresh()
        change = hass.states.get(entity).attributes["changes"][0]
        assert change["removed"] == [{"start": "12:00", "end": "13:00"}]


async def test_shared_queues_have_independent_events(hass, entry, schedule):
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id="other_queue",
        title="Other",
        data={"operator": schedule["initiator"], "queue": "2.1"},
    )
    other.add_to_hass(hass)
    with patch(FETCH, return_value=[schedule, {**schedule, "queue": "2.1"}]) as fetch:
        first, first_event = await setup(hass, entry)
        if other.state.value != "loaded":
            await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        other_event = event_id(hass, other)
        changed = deepcopy(schedule)
        changed["today"][12] = 1
        fetch.return_value = [changed, {**schedule, "queue": "2.1"}]
        await first.async_refresh()
        assert hass.states.get(first_event).state != "unknown"
        assert hass.states.get(other_event).state == "unknown"
        assert first.source is hass.data[DOMAIN][other.entry_id].source


@pytest.fixture
def notification_blueprint(hass):
    destination = Path(
        hass.config.path(
            "blueprints/automation/alerts_energy_outages/schedule_changes.yaml"
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(BLUEPRINT.read_text(encoding="utf-8"), encoding="utf-8")


@pytest.mark.parametrize("default_action", [False, True])
async def test_notification_blueprint_runs_and_skips_replays(
    hass, entry, schedule, notification_blueprint, default_action
):
    calls = async_mock_service(
        hass,
        "persistent_notification" if default_action else "test",
        "create" if default_action else "notify",
    )
    with patch(FETCH, return_value=[schedule]) as fetch:
        coordinator, entity = await setup(hass, entry)
        inputs = {"schedule_event": entity}
        if not default_action:
            inputs["notification_actions"] = [
                {
                    "service": "test.notify",
                    "data": {"message": "{{ notification_message }}"},
                }
            ]
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "alias": "Schedule notifications",
                        "use_blueprint": {
                            "path": "alerts_energy_outages/schedule_changes.yaml",
                            "input": inputs,
                        },
                    }
                ]
            },
        )
        await hass.async_block_till_done()
        changed = deepcopy(schedule)
        changed["today"][12] = 3
        fetch.return_value = [changed]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 1
        # HA 2024.6 can use the same event timestamp for consecutive updates.
        changed["today"] = [0] * 24
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 2
        assert "без відключень за графіком" in calls[1].data["message"]
        assert "Додано: 12:30–13:00" in calls[0].data["message"]
        assert "Скасовано: 12:00–12:30" in calls[0].data["message"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(calls) == 2
        # A restored timestamp becoming available must not deliver the old event.
        previous = hass.states.get(entity)
        hass.states.async_set(entity, "unavailable")
        hass.states.async_set(entity, previous.state, dict(previous.attributes))
        await hass.async_block_till_done()
        assert len(calls) == 2
