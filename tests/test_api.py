"""Transport and public queue contract regressions."""

from copy import deepcopy

import pytest
from aiohttp import ClientError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.alerts_energy_outages.api import (
    AlertsEnergyApi,
    AlertsEnergyApiError,
)
from custom_components.alerts_energy_outages.const import API_URL, DEFAULT_OPERATOR


async def test_dynamic_queues(hass, aioclient_mock, public_rows):
    aioclient_mock.get(API_URL, json=public_rows)
    api = AlertsEnergyApi(async_get_clientsession(hass))
    assert await api.async_get_queues(DEFAULT_OPERATOR) == ["1.1", "2.1", "60.1"]


async def test_missing_queue_is_explicit(hass, aioclient_mock, public_rows):
    aioclient_mock.get(API_URL, json=public_rows)
    api = AlertsEnergyApi(async_get_clientsession(hass))
    result = await api.async_get_schedule(DEFAULT_OPERATOR, "2.2")
    assert result == {
        "queue": "2.2",
        "initiator": DEFAULT_OPERATOR,
        "schedule_found": False,
    }


async def test_days_are_not_coupled(hass, aioclient_mock, schedule):
    schedule["tomorrow"] = []
    aioclient_mock.get(API_URL, json=[schedule])
    result = await AlertsEnergyApi(async_get_clientsession(hass)).async_get_schedule(
        DEFAULT_OPERATOR, "2.2"
    )
    assert result["today"] == schedule["today"]
    assert result["tomorrow"] == []
    assert result["schedule_found"] is True


@pytest.mark.parametrize("payload", [{}, [None], ["row"], [1]])
async def test_malformed_response(hass, aioclient_mock, payload):
    aioclient_mock.get(API_URL, json=payload)
    with pytest.raises(AlertsEnergyApiError, match="Unexpected response format"):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_schedules()


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_errors(hass, aioclient_mock, status):
    aioclient_mock.get(API_URL, status=status)
    with pytest.raises(AlertsEnergyApiError):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_schedules()


@pytest.mark.parametrize("error", [ClientError("network"), TimeoutError()])
async def test_connection_errors(hass, aioclient_mock, error):
    aioclient_mock.get(API_URL, exc=error)
    with pytest.raises(AlertsEnergyApiError):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_schedules()


async def test_invalid_json(hass, aioclient_mock):
    aioclient_mock.get(
        API_URL, text="not json", headers={"Content-Type": "application/json"}
    )
    with pytest.raises(AlertsEnergyApiError):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_schedules()


async def test_queue_filter(hass, aioclient_mock, public_rows):
    other = deepcopy(public_rows[0])
    other["initiator"] = "other"
    aioclient_mock.get(
        API_URL,
        json=public_rows + [other, {"initiator": DEFAULT_OPERATOR, "queue": None}],
    )
    assert await AlertsEnergyApi(async_get_clientsession(hass)).async_get_queues(
        DEFAULT_OPERATOR
    ) == ["1.1", "2.1", "60.1"]


async def test_region_endpoints_and_operator_isolation(hass, aioclient_mock, schedule):
    from custom_components.alerts_energy_outages.const import API_BASE_URL

    area = "dnipropetrovska-oblast"
    rows = []
    for operator, queue in [("oblenergo", "2.2"), ("cek", "7.1")]:
        row = deepcopy(schedule)
        row.update(initiator=operator, queue=queue)
        rows.append(row)
    url = f"{API_BASE_URL}/source-registry/areas/{area}/shutdowns"
    aioclient_mock.get(url, json=rows)
    api = AlertsEnergyApi(async_get_clientsession(hass))
    assert await api.async_get_queues("cek", area) == ["7.1"]
    assert (await api.async_get_schedule("oblenergo", "2.2", area))[
        "initiator"
    ] == "oblenergo"
    assert (await api.async_get_schedule("cek", "2.2", area))["schedule_found"] is False
    assert all(str(request[1]) == url for request in aioclient_mock.mock_calls)


async def test_directory_and_operators(hass, directory):
    api = AlertsEnergyApi(async_get_clientsession(hass))
    areas = await api.async_get_areas()
    assert {area.slug for area in areas} == {
        "kyiv",
        "kyivska-oblast",
        "dnipropetrovska-oblast",
    }
    assert (await api.async_get_children(directory["community"]["katottg"]))[
        0
    ].name == "Буча"
    assert await api.async_get_operators("kyivska-oblast") == {
        "regional_operator": "Test network",
        "alternate_operator": "Other network",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"katottg": "bad"},
        {"level": True},
        {"name": ""},
        {"parent_katottg": "other"},
        {"slug": "../outside"},
        {"category": None},
    ],
)
async def test_invalid_territory_is_not_a_choice(
    hass, aioclient_mock, directory, change
):
    from custom_components.alerts_energy_outages.const import API_BASE_URL

    row = {**directory["root"][0], **change}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE_URL}/atus", json=[row])
    with pytest.raises(AlertsEnergyApiError, match="territory format"):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_areas()


async def test_duplicate_directory_ids(hass, aioclient_mock, directory):
    from custom_components.alerts_energy_outages.const import API_BASE_URL

    row = directory["root"][0]
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE_URL}/atus", json=[row, row])
    with pytest.raises(AlertsEnergyApiError, match="Duplicate territory"):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_areas()


@pytest.mark.parametrize(
    "change", [{"areaSlug": "another-area"}, {"slug": None}, {"supplierName": None}]
)
async def test_malformed_supplier(hass, aioclient_mock, change):
    from custom_components.alerts_energy_outages.const import API_BASE_URL

    row = {"areaSlug": "kyiv", "slug": "operator", "supplierName": "Network", **change}
    aioclient_mock.get(
        f"{API_BASE_URL}/source-registry/areas/kyiv/suppliers", json=[row]
    )
    with pytest.raises(AlertsEnergyApiError, match="operator format"):
        await AlertsEnergyApi(async_get_clientsession(hass)).async_get_operators("kyiv")


async def test_village_name_does_not_use_incorrect_source_prefix(
    hass, aioclient_mock, directory
):
    from custom_components.alerts_energy_outages.const import API_BASE_URL

    row = {
        **directory["city"],
        "name": "Village",
        "category": "C",
        "full_name": "city Village",
    }
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE_URL}/atus/{row['parent_katottg']}", json=[row])
    result = await AlertsEnergyApi(async_get_clientsession(hass)).async_get_children(
        row["parent_katottg"]
    )
    assert result[0].name == "Village"
