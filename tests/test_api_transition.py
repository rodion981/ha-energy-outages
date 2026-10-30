"""Authenticated API transition, durable quota control and real HA consumers."""

import asyncio
import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from aiohttp import ClientError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.alerts_energy_outages.api import (
    STORAGE_KEY,
    AlertsEnergyApiError,
    async_get_api,
    normalize_row,
)
from custom_components.alerts_energy_outages.const import (
    API_BASE_URL,
    API_URL,
    DEFAULT_OPERATOR,
    DOMAIN,
)
from custom_components.alerts_energy_outages.credentials import API_KEY
from custom_components.alerts_energy_outages.diagnostics import (
    async_get_config_entry_diagnostics,
)


def wire(row):
    """Model upstream snake_case without changing existing domain fixtures."""
    result = deepcopy(row)
    for day in ("today", "tomorrow"):
        for suffix in ("Date", "Status", "Possible"):
            if (key := f"{day}{suffix}") in result:
                result[f"{day}_{suffix.lower()}"] = result.pop(key)
    return result


def entity_ids(hass, entry):
    return {
        item.unique_id.removeprefix(entry.unique_id + "_"): item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


async def tick(hass, freezer, seconds):
    when = dt_util.utcnow() + timedelta(seconds=seconds)
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def test_identity_shared_durable_and_headers(
    hass, hass_storage, aioclient_mock, schedule
):
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    aioclient_mock.get(f"{API_BASE_URL}/atus", json=[])
    first, other = await asyncio.gather(async_get_api(hass), async_get_api(hass))
    assert first is other
    await first.async_get_schedules()
    await other.async_get_areas()
    headers = [call[3] for call in aioclient_mock.mock_calls]
    identity = headers[0]["X-HA-Instance-ID"]
    assert UUID(identity).version == 4
    assert all(header["X-HA-Instance-ID"] == identity for header in headers)
    assert all(header["Authorization"] == f"Bearer {API_KEY}" for header in headers)
    stored = hass_storage[STORAGE_KEY]["data"]
    assert stored["instance_id"] == identity
    assert API_KEY not in json.dumps(stored)
    hass.data[DOMAIN].pop("_api")
    restored = await async_get_api(hass)
    assert restored is not first
    assert await restored.async_get_schedules() == await first.async_get_schedules()
    assert aioclient_mock.call_count == 2
    assert hass_storage[STORAGE_KEY]["data"]["instance_id"] == identity


async def test_flows_setup_reload_and_manual_refresh_share_quota(
    hass, hass_storage, aioclient_mock, directory, entry, freezer
):
    api = await async_get_api(hass)
    assert await api.async_get_queues(DEFAULT_OPERATOR)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    initial = coordinator.last_successful_update
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await tick(hass, freezer, 899)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert hass.data[DOMAIN][entry.entry_id].last_successful_update == initial

    def calls():
        return sum(str(call[1]) == API_URL for call in aioclient_mock.mock_calls)

    assert calls() == 1
    await tick(hass, freezer, 2)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert calls() == 2


async def test_concurrent_readers_and_independent_areas(hass, aioclient_mock, schedule):
    other_url = f"{API_BASE_URL}/source-registry/areas/kyivska-oblast/shutdowns"
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    aioclient_mock.get(other_url, json=[wire(schedule)])
    api = await async_get_api(hass)
    results = await asyncio.gather(*(api.async_get_schedules() for _ in range(8)))
    assert aioclient_mock.call_count == 1
    results[0][0]["today"][0] = 99
    assert (await api.async_get_schedules())[0]["today"][0] != 99
    await api.async_get_schedules("kyivska-oblast")
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize("header", ["1800", "Wed, 07 Oct 2026 09:30:00 GMT"])
async def test_retry_after_survives_restart_and_early_manual_requests(
    hass, hass_storage, aioclient_mock, freezer, header
):
    aioclient_mock.get(API_URL, status=429, headers={"Retry-After": header})
    api = await async_get_api(hass)
    with pytest.raises(AlertsEnergyApiError) as err:
        await api.async_get_schedules()
    assert err.value.retry_after == 1800
    hass.data[DOMAIN].pop("_api")
    api = await async_get_api(hass)
    await tick(hass, freezer, 900)
    for _ in range(3):
        with pytest.raises(AlertsEnergyApiError):
            await api.async_get_schedules()
    assert aioclient_mock.call_count == 1
    await tick(hass, freezer, 900)
    with pytest.raises(AlertsEnergyApiError):
        await api.async_get_schedules()
    assert aioclient_mock.call_count == 2


async def test_progressive_backoff_and_success_reset(
    hass, aioclient_mock, freezer, schedule
):
    aioclient_mock.get(API_URL, status=503)
    api = await async_get_api(hass)
    for delay in (900, 1800, 3600, 7200, 14400, 28800, 57600, 86400, 86400):
        with pytest.raises(AlertsEnergyApiError) as err:
            await api.async_get_schedules()
        assert err.value.retry_after == delay
        await tick(hass, freezer, delay)
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    await api.async_get_schedules()
    await tick(hass, freezer, 900)
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    with pytest.raises(AlertsEnergyApiError) as err:
        await api.async_get_schedules()
    assert err.value.retry_after == 900


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
async def test_failures_do_not_expose_credential_or_follow_redirect(
    hass, aioclient_mock, caplog, status
):
    aioclient_mock.get(
        API_URL,
        status=status,
        text=API_KEY,
        headers={"Location": "https://example.invalid/leak", "Retry-After": "invalid"},
    )
    api = await async_get_api(hass)
    with pytest.raises(AlertsEnergyApiError) as err:
        await api.async_get_schedules()
    assert API_KEY not in str(err.value)
    assert API_KEY not in caplog.text
    assert aioclient_mock.call_count == 1


async def test_transport_exception_text_is_sanitized(hass, aioclient_mock, caplog):
    aioclient_mock.get(API_URL, exc=ClientError(API_KEY))
    api = await async_get_api(hass)
    with pytest.raises(AlertsEnergyApiError) as err:
        await api.async_get_schedules()
    assert API_KEY not in str(err.value)
    assert API_KEY not in caplog.text


async def test_persisted_cache_starts_offline_with_truthful_health(
    hass, hass_storage, aioclient_mock, entry, schedule, freezer
):
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    api = await async_get_api(hass)
    await api.async_get_schedules()
    receipt = dt_util.utcnow()
    hass.data[DOMAIN].pop("_api")
    await tick(hass, freezer, 901)
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert not coordinator.last_update_success
    assert coordinator.last_successful_update == receipt
    assert hass.states.get(ids["today"]).state != "unavailable"
    assert hass.states.get(ids["today"]).attributes["data_is_cached"]
    assert hass.states.get(ids["data_status"]).state == "connection_error"
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert API_KEY not in json.dumps(diagnostics)
    identity = hass_storage[STORAGE_KEY]["data"]["instance_id"]
    assert identity not in json.dumps(diagnostics)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1


async def test_persisted_cache_date_expiry_and_new_emergency_replace_old(
    hass, aioclient_mock, entry, schedule, freezer
):
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=901))
    emergency = wire(schedule)
    emergency["today_status"] = "EmergencyShutdowns"
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=[emergency])
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert hass.states.get(ids["today"]).state == "unavailable"
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.data[DOMAIN].pop("_api")
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    await tick(hass, freezer, 86400)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ids["today"]).state == "unavailable"


async def test_snake_case_actual_entities_and_source_link(
    hass, aioclient_mock, entry, schedule
):
    data = wire(schedule)
    data["today_possible"] = [1] + [0] * 23
    aioclient_mock.get(API_URL, json=[data])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = entity_ids(hass, entry)
    today = hass.states.get(ids["today"])
    assert today.attributes["date"] == "2026-10-07"
    assert today.attributes["outage_type"] == "mixed"
    assert today.attributes["possible_hours"] == data["today_possible"]
    assert len(ids) == 10


@pytest.mark.parametrize("value", [None, [], "", "WaitingForSchedule"])
def test_new_fields_take_precedence_even_when_empty(value):
    result = normalize_row({"todayPossible": [1] * 24, "today_possible": value})
    assert result["todayPossible"] == value


async def test_new_supplier_fields(hass, aioclient_mock):
    aioclient_mock.get(
        f"{API_BASE_URL}/source-registry/areas/kyiv/suppliers",
        json=[{"slug": "operator", "area_slug": "kyiv", "supplier_name": "Network"}],
    )
    assert await (await async_get_api(hass)).async_get_operators("kyiv") == {
        "operator": "Network"
    }


async def test_failed_durable_save_prevents_network(hass, aioclient_mock):
    with patch(
        "custom_components.alerts_energy_outages.api.Store.async_save",
        side_effect=OSError("disk"),
    ):
        with pytest.raises(AlertsEnergyApiError, match="persist"):
            await async_get_api(hass)
    assert aioclient_mock.call_count == 0


async def test_cancelled_request_cannot_bypass_persisted_cooldown(
    hass, aioclient_mock, schedule
):
    api = await async_get_api(hass)
    started = asyncio.Event()

    async def blocked(path):
        started.set()
        await asyncio.Event().wait()

    with patch.object(api, "_async_fetch_rows", side_effect=blocked):
        task = asyncio.create_task(api.async_get_schedules())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    hass.data[DOMAIN].pop("_api")
    restored = await async_get_api(hass)
    with pytest.raises(AlertsEnergyApiError):
        await restored.async_get_schedules()
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "state",
    [None, [], {"next_request": "bad"}, {"next_request": 1e300}, {"next_request": -1}],
)
async def test_corrupt_persisted_request_is_ignored(
    hass, hass_storage, aioclient_mock, state
):
    api = await async_get_api(hass)
    api.restore({"source-registry/areas/kyiv/shutdowns": state, "unrelated": {}})
    aioclient_mock.get(API_URL, json=[])
    assert await api.async_get_schedules() == []
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, 0),
        ("bad", 0),
        ("0", 0),
        ("172800", 172800),
        ("Wed, 07 Oct 2026 10:00:00", 3600),
        ("9" * 400, 0),
    ],
)
def test_retry_after_header_validation(header, expected):
    from custom_components.alerts_energy_outages.api import AlertsEnergyApi

    assert AlertsEnergyApi._retry_after(header) == expected


async def test_real_flow_and_setup_reuse_queue_discovery(
    hass, directory, aioclient_mock
):
    form = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    form = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"area": "kyiv"}
    )
    form = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"operator": DEFAULT_OPERATOR}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"queue": "2.2"}
    )
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.state.value == "loaded"
    assert sum(str(call[1]) == API_URL for call in aioclient_mock.mock_calls) == 1


async def test_real_coordinator_timer_honors_long_retry_after(
    hass, entry, schedule, aioclient_mock, freezer
):
    aioclient_mock.get(API_URL, json=[wire(schedule)])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=429, headers={"Retry-After": "3600"})
    await tick(hass, freezer, 901)
    source = hass.data[DOMAIN][entry.entry_id].source
    assert not source.last_update_success
    assert source.update_interval == timedelta(hours=1)
    assert aioclient_mock.call_count == 1
    await tick(hass, freezer, 901)
    assert aioclient_mock.call_count == 1
    await tick(hass, freezer, 2700)
    assert aioclient_mock.call_count == 2


async def test_legacy_interval_is_raised_without_changing_identity(
    hass, entry, schedule
):
    from custom_components.alerts_energy_outages.const import CONF_SCAN_INTERVAL

    previous_data = dict(entry.data)
    previous_identity = entry.unique_id
    hass.config_entries.async_update_entry(
        entry, minor_version=2, options={CONF_SCAN_INTERVAL: 3, "retained": True}
    )
    with patch(
        "custom_components.alerts_energy_outages.api.AlertsEnergyApi.async_get_schedules",
        return_value=[schedule],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.options == {CONF_SCAN_INTERVAL: 15, "retained": True}
    assert entry.unique_id == previous_identity
    assert entry.data == previous_data


@pytest.mark.parametrize("language", ["en", "uk"])
def test_area_selection_links_to_data_source(language):
    from pathlib import Path

    data = json.loads(
        Path(
            f"custom_components/alerts_energy_outages/translations/{language}.json"
        ).read_text(encoding="utf-8")
    )
    for step in ("user", "reconfigure"):
        assert (
            "[Alerts Energy](https://alerts.energy/)"
            in data["config"]["step"][step]["description"]
        )
