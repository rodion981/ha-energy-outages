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
