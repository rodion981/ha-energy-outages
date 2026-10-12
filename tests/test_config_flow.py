"""Regional setup, source failures, exact selections and stable identities."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.config_flow import (
    PREVIOUS_LOCALITY,
    RETRY_LOCALITY,
    SKIP_LOCALITY,
)
from custom_components.alerts_energy_outages.const import (
    CONF_ENTITY_UNIQUE_ID,
    DEFAULT_OPERATOR,
    DOMAIN,
)

API = "custom_components.alerts_energy_outages.config_flow.AlertsEnergyApi"
SETUP = "custom_components.alerts_energy_outages.async_setup_entry"


async def choose(hass, flow, data, expected_step):
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], data)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == expected_step
    return result


async def to_queue(hass, area="kyiv", operator=DEFAULT_OPERATOR, context=None):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=context or {"source": config_entries.SOURCE_USER},
        data={"area": area},
    )
    if area != "kyiv":
        result = await choose(hass, result, {"locality": SKIP_LOCALITY}, "operator")
    return await choose(hass, result, {"operator": operator}, "queue")


async def test_user_discovers_regions_and_queues(hass, directory):
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert form["step_id"] == "user"
    schema = form["data_schema"].schema
    selector = next(iter(schema.values()))
    assert {item["value"] for item in selector.config["options"]} == {
        "kyiv",
        "kyivska-oblast",
        "dnipropetrovska-oblast",
    }
    form = await choose(hass, form, {"area": "kyiv"}, "operator")
    form = await choose(hass, form, {"operator": DEFAULT_OPERATOR}, "queue")
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"name": "Home", "queue": "60.1"}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["area"] == "kyiv"
    assert result["data"]["locality_name"] == "Київ"
    assert result["data"]["operator"] == DEFAULT_OPERATOR
    assert result["data"]["queue"] == "60.1"
    assert result["result"].unique_id == f"{DEFAULT_OPERATOR}_60.1"
    assert result["result"].minor_version == 2


async def test_region_district_community_city(hass, directory):
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"area": "kyivska-oblast"}
    )
    assert form["step_id"] == "locality"
    for key in ["district", "community"]:
        form = await choose(
            hass, form, {"locality": directory[key]["katottg"]}, "locality"
        )
    form = await choose(
        hass, form, {"locality": directory["city"]["katottg"]}, "operator"
    )
    form = await choose(hass, form, {"operator": "regional_operator"}, "queue")
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.2"}
        )
        await hass.async_block_till_done()
    assert result["title"] == "Буча"
    assert result["data"]["locality_id"] == directory["city"]["katottg"]
    assert result["result"].unique_id == "kyivska-oblast_regional_operator_2.2"


async def test_locality_back_and_skip(hass, directory):
    hass.config.language = "uk"
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"area": "kyivska-oblast"}
    )
    form = await choose(
        hass, form, {"locality": directory["district"]["katottg"]}, "locality"
    )
    form = await choose(hass, form, {"locality": PREVIOUS_LOCALITY}, "locality")
    assert form["description_placeholders"]["territory"] == directory["area"]["name"]
    form = await choose(hass, form, {"locality": SKIP_LOCALITY}, "operator")
    assert not form["errors"]


async def test_duplicate_old_kyiv(hass, entry, directory):
    form = await to_queue(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"queue": "2.2"}
    )
    assert result["reason"] == "already_configured"


async def test_identical_operator_queue_in_different_regions(hass, directory):
    ids = []
    with patch(SETUP, return_value=True):
        for area in ["kyivska-oblast", "dnipropetrovska-oblast"]:
            form = await to_queue(hass, area, "regional_operator")
            result = await hass.config_entries.flow.async_configure(
                form["flow_id"], {"queue": "2.2"}
            )
            await hass.async_block_till_done()
            ids.append(result["result"].unique_id)
    assert len(set(ids)) == 2


@pytest.mark.parametrize("method,error", [("async_get_areas", "cannot_connect")])
async def test_directory_connection_feedback_and_retry(hass, directory, method, error):
    with patch(f"{API}.{method}", side_effect=AlertsEnergyApiError("offline")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["errors"] == {"base": error}
    assert not result["data_schema"].schema
    result = await choose(hass, result, {}, "user")
    assert not result["errors"]
    assert result["data_schema"].schema


async def test_empty_regions(hass):
    with patch(f"{API}.async_get_areas", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
    assert result["errors"] == {"base": "no_areas"}


@pytest.mark.parametrize(
    "method,expected",
    [("async_get_operators", "no_operators"), ("async_get_queues", "no_queues")],
)
async def test_empty_downstream_source(hass, directory, method, expected):
    with patch(
        f"{API}.{method}", return_value={} if method == "async_get_operators" else []
    ):
        if method == "async_get_operators":
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data={"area": "kyiv"}
            )
        else:
            result = await to_queue(hass)
    assert result["errors"] == {"base": expected}
    assert str(next(iter(result["data_schema"].schema))) == "action"


async def test_changed_queue_not_silently_mapped(hass, directory):
    form = await to_queue(hass)
    with patch(f"{API}.async_get_queues", return_value=["2.1"]):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.2"}
        )
    assert result["errors"] == {"queue": "invalid_queue"}


async def test_reconfigure_identity(hass, entry, directory):
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        form = await to_queue(
            hass,
            "kyivska-oblast",
            "regional_operator",
            {"source": "reconfigure", "entry_id": entry.entry_id},
        )
        assert entry.data["queue"] == "2.2"
        assert "area" not in entry.data
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.1", "name": "Alerts Energy"}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "kyivska-oblast_regional_operator_2.1"
    assert entry.data[CONF_ENTITY_UNIQUE_ID] == f"{DEFAULT_OPERATOR}_2.2"
    assert entry.data["area"] == "kyivska-oblast"
    assert entry.data["locality_id"] is None


async def test_reconfigure_duplicate(hass, entry, directory):
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        unique_id="kyivska-oblast_regional_operator_2.1",
        data={
            "area": "kyivska-oblast",
            "operator": "regional_operator",
            "queue": "2.1",
        },
        minor_version=2,
    )
    other.add_to_hass(hass)
    form = await to_queue(
        hass,
        "kyivska-oblast",
        "regional_operator",
        {"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"queue": "2.1"}
    )
    assert result["reason"] == "already_configured"
    assert entry.unique_id == f"{DEFAULT_OPERATOR}_2.2"


async def test_reusing_preserved_identity(hass, entry, directory):
    hass.config_entries.async_update_entry(
        entry,
        unique_id=f"{DEFAULT_OPERATOR}_2.1",
        data={
            "operator": DEFAULT_OPERATOR,
            "queue": "2.1",
            CONF_ENTITY_UNIQUE_ID: f"{DEFAULT_OPERATOR}_2.2",
        },
    )
    with patch(SETUP, return_value=True):
        form = await to_queue(hass)
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.2"}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENTITY_UNIQUE_ID] != entry.data[CONF_ENTITY_UNIQUE_ID]


@pytest.mark.parametrize("stage", ["locality", "operator", "queue"])
async def test_downstream_connection_retry(hass, directory, stage):
    method = {
        "locality": "async_get_children",
        "operator": "async_get_operators",
        "queue": "async_get_queues",
    }[stage]
    with patch(f"{API}.{method}", side_effect=AlertsEnergyApiError("offline")):
        if stage == "locality":
            form = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data={"area": "kyivska-oblast"}
            )
        elif stage == "operator":
            form = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data={"area": "kyiv"}
            )
        else:
            form = await to_queue(hass)
    assert form["errors"] == {"base": "cannot_connect"}
    result = await choose(
        hass, form, {"locality": RETRY_LOCALITY} if stage == "locality" else {}, stage
    )
    assert not result["errors"]


@pytest.mark.parametrize("stage", ["area", "locality", "operator"])
async def test_removed_choice_feedback(hass, directory, stage):
    if stage == "area":
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        method = "async_get_areas"
        updated = []
        data = {"area": "kyiv"}
    elif stage == "operator":
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={"area": "kyiv"}
        )
        method = "async_get_operators"
        updated = {"other": "Other"}
        data = {"operator": DEFAULT_OPERATOR}
    else:
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={"area": "kyivska-oblast"}
        )
        method = "async_get_children"
        updated = []
        data = {"locality": directory["district"]["katottg"]}
    with patch(f"{API}.{method}", return_value=updated):
        result = await hass.config_entries.flow.async_configure(form["flow_id"], data)
    if stage == "area":
        assert result["errors"] == {"base": "no_areas"}
    else:
        key = "operator" if stage == "operator" else "locality"
        assert result["errors"] == (
            {"base": "no_localities"}
            if stage == "locality"
            else {key: "invalid_selection"}
        )


async def test_reconfigure_failure_and_cancel_leave_entry_unchanged(
    hass, entry, directory
):
    previous = dict(entry.data)
    form = await to_queue(
        hass,
        "kyivska-oblast",
        "regional_operator",
        {"source": "reconfigure", "entry_id": entry.entry_id},
    )
    with patch(f"{API}.async_get_queues", side_effect=AlertsEnergyApiError("offline")):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.1"}
        )
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == previous
    hass.config_entries.flow.async_abort(form["flow_id"])
    assert entry.data == previous
    assert entry.unique_id == f"{DEFAULT_OPERATOR}_2.2"


async def test_same_regional_schedule_in_another_city_is_duplicate(hass, directory):
    with patch(SETUP, return_value=True):
        form = await to_queue(hass, "kyivska-oblast", "regional_operator")
        await hass.config_entries.flow.async_configure(
            form["flow_id"], {"queue": "2.2"}
        )
        await hass.async_block_till_done()
    form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"area": "kyivska-oblast"}
    )
    for key in ["district", "community"]:
        form = await choose(
            hass, form, {"locality": directory[key]["katottg"]}, "locality"
        )
    form = await choose(
        hass, form, {"locality": directory["city"]["katottg"]}, "operator"
    )
    form = await choose(hass, form, {"operator": "regional_operator"}, "queue")
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"queue": "2.2"}
    )
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("stage", ["operator", "queue"])
async def test_no_data_can_return_to_previous_choice(hass, directory, stage):
    method = "async_get_operators" if stage == "operator" else "async_get_queues"
    with patch(f"{API}.{method}", return_value={} if stage == "operator" else []):
        if stage == "operator":
            form = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data={"area": "kyiv"}
            )
        else:
            form = await to_queue(hass)
    form = await choose(
        hass, form, {"action": "back"}, "user" if stage == "operator" else "operator"
    )
    assert not form["errors"]
