"""Shared Home Assistant fixtures."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alerts_energy_outages.const import DEFAULT_OPERATOR, DOMAIN


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading the integration from this repository."""


@pytest.fixture(autouse=True)
def fixed_time(freezer):
    """Use a stable day and a known Kyiv outage boundary."""
    freezer.move_to(datetime(2026, 10, 7, 9, tzinfo=UTC))


@pytest.fixture
def schedule():
    hours = [0] * 24
    hours[12] = 2
    return {
        "initiator": DEFAULT_OPERATOR,
        "queue": "2.2",
        "today": hours,
        "tomorrow": [0] * 24,
        "todayDate": "2026-10-07",
        "tomorrowDate": "2026-10-08",
        "todayStatus": "ScheduleApplies",
        "tomorrowStatus": "ScheduleApplies",
        "updated": "2026-10-07T08:00:00Z",
    }


@pytest.fixture
def entry(hass):
    result = MockConfigEntry(
        domain=DOMAIN,
        title="Alerts Energy",
        unique_id=f"{DEFAULT_OPERATOR}_2.2",
        data={"operator": DEFAULT_OPERATOR, "queue": "2.2"},
    )
    result.add_to_hass(hass)
    return result


@pytest.fixture
def public_rows(schedule):
    rows = []
    for queue in ("1.1", "2.1", "60.1"):
        row = deepcopy(schedule)
        row["queue"] = queue
        rows.append(row)
    return rows
