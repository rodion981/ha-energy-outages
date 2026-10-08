"""Creation, error feedback and identity-preserving reconfiguration."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alerts_energy_outages.api import AlertsEnergyApiError
from custom_components.alerts_energy_outages.const import (
    CONF_ENTITY_UNIQUE_ID,
    DEFAULT_OPERATOR,
    DOMAIN,
)

QUEUES_METHOD = "custom_components.alerts_energy_outages.config_flow.AlertsEnergyApi.async_get_queues"


async def test_user_discovers_queues(hass):
    with (
        patch(QUEUES_METHOD, return_value=["1.1", "60.1"]),
        patch(
            "custom_components.alerts_energy_outages.async_setup_entry",
            return_value=True,
        ),
    ):
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert form["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"name": "Home", "queue": "60.1"}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"operator": DEFAULT_OPERATOR, "queue": "60.1"}
    assert result["result"].unique_id == f"{DEFAULT_OPERATOR}_60.1"


async def test_duplicate(hass, entry):
    with patch(QUEUES_METHOD, return_value=["2.2"]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"queue": "2.2"},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_connection_feedback(hass):
    with patch(QUEUES_METHOD, side_effect=AlertsEnergyApiError("offline")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_empty_queues(hass):
    with patch(QUEUES_METHOD, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["errors"] == {"base": "no_queues"}


async def test_changed_queue_not_silently_mapped(hass):
    with patch(QUEUES_METHOD, return_value=["2.1"]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"queue": "2.2"},
        )
    assert result["errors"] == {"queue": "invalid_queue"}


async def test_reconfigure_identity(hass, entry):
    with (
        patch(QUEUES_METHOD, return_value=["2.1"]),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={"queue": "2.1", "name": "Alerts Energy"},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == f"{DEFAULT_OPERATOR}_2.1"
    assert entry.data[CONF_ENTITY_UNIQUE_ID] == f"{DEFAULT_OPERATOR}_2.2"
    assert entry.data["queue"] == "2.1"


async def test_reconfigure_duplicate(hass, entry):
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        unique_id=f"{DEFAULT_OPERATOR}_2.1",
        data={"operator": DEFAULT_OPERATOR, "queue": "2.1"},
    )
    other.add_to_hass(hass)
    with patch(QUEUES_METHOD, return_value=["2.1"]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={"queue": "2.1"},
        )
    assert result["reason"] == "already_configured"
    assert entry.data["queue"] == "2.2"


async def test_reusing_a_preserved_identity(hass, entry):
    hass.config_entries.async_update_entry(
        entry,
        unique_id=f"{DEFAULT_OPERATOR}_2.1",
        data={
            "operator": DEFAULT_OPERATOR,
            "queue": "2.1",
            CONF_ENTITY_UNIQUE_ID: f"{DEFAULT_OPERATOR}_2.2",
        },
    )
    with (
        patch(QUEUES_METHOD, return_value=["2.2"]),
        patch(
            "custom_components.alerts_energy_outages.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"queue": "2.2"},
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENTITY_UNIQUE_ID] != entry.data[CONF_ENTITY_UNIQUE_ID]
