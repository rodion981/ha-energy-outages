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


@pytest.fixture
def directory(aioclient_mock, schedule):
    """A synthetic region/district/community/city directory with exact suppliers."""
    from custom_components.alerts_energy_outages.const import API_BASE_URL, API_URL

    def territory(katottg, slug, name, category, level, parent=None):
        return {
            "katottg": katottg,
            "slug": slug,
            "name": name,
            "full_name": name,
            "category": category,
            "level": level,
            "parent_katottg": parent,
        }

    kyiv = territory("UA80000000000093317", "kyiv", "Київ", "K", 1)
    area = territory(
        "UA32000000000030281", "kyivska-oblast", "Київська область", "O", 1
    )
    other = territory(
        "UA12000000000090473",
        "dnipropetrovska-oblast",
        "Дніпропетровська область",
        "O",
        1,
    )
    district = territory(
        "UA32080000000084076",
        "buchanskij-rayon",
        "Бучанський район",
        "P",
        2,
        area["katottg"],
    )
    community = territory(
        "UA32080070000050759",
        "buchanska-terytorialna-hromada",
        "Бучанська громада",
        "H",
        3,
        district["katottg"],
    )
    city = territory(
        "UA32080070010051388", "misto-bucha", "Буча", "M", 4, community["katottg"]
    )
    root = [kyiv, area, other]
    aioclient_mock.get(f"{API_BASE_URL}/atus", json=root)
    for parent, children in [
        (area, [district]),
        (district, [community]),
        (community, [city]),
        (other, []),
    ]:
        aioclient_mock.get(f"{API_BASE_URL}/atus/{parent['katottg']}", json=children)
    for current in root:
        operator = (
            DEFAULT_OPERATOR if current["slug"] == "kyiv" else "regional_operator"
        )
        operators = {operator: "Test network", "alternate_operator": "Other network"}
        aioclient_mock.get(
            f"{API_BASE_URL}/source-registry/areas/{current['slug']}/suppliers",
            json=[
                {"areaSlug": current["slug"], "slug": key, "supplierName": label}
                for key, label in operators.items()
            ],
        )
        rows = []
        for queue in ["1.1", "2.1", "2.2", "60.1"]:
            row = deepcopy(schedule)
            row.update(initiator=operator, queue=queue)
            rows.append(row)
        aioclient_mock.get(
            f"{API_BASE_URL}/source-registry/areas/{current['slug']}/shutdowns",
            json=rows,
        )
    return {
        "root": root,
        "area": area,
        "district": district,
        "community": community,
        "city": city,
        "kyiv_url": API_URL,
    }
