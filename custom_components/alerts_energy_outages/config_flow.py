"""Config flow for Alerts Energy Outages."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AlertsEnergyApi, AlertsEnergyApiError
from .const import (
    CONF_ENTITY_UNIQUE_ID,
    CONF_OPERATOR,
    DEFAULT_OPERATOR,
    DEFAULT_QUEUE,
    DOMAIN,
)


# HA's dynamic registration is covered by config flow runtime tests.
class AlertsEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle an Alerts Energy config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._queues: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an entry for a Kyiv DTEK queue."""
        return await self._async_configure("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the owner select a new exact queue while retaining entity IDs."""
        return await self._async_configure("reconfigure", user_input)

    async def _async_configure(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = None
        if step_id == "reconfigure":
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if entry is None or entry.domain != DOMAIN:
                return self.async_abort(reason="invalid_entry")
        operator = (
            entry.data.get(CONF_OPERATOR, DEFAULT_OPERATOR)
            if entry
            else DEFAULT_OPERATOR
        )
        try:
            self._queues = await AlertsEnergyApi(
                async_get_clientsession(self.hass)
            ).async_get_queues(operator)
        except AlertsEnergyApiError:
            errors["base"] = "cannot_connect"
        else:
            if not self._queues:
                errors["base"] = "no_queues"

        if user_input is not None and not errors:
            queue = user_input["queue"]
            if queue not in self._queues:
                errors["queue"] = "invalid_queue"
            else:
                unique_id = f"{operator}_{queue}"
                await self.async_set_unique_id(unique_id)
                if entry is None or unique_id != entry.unique_id:
                    self._abort_if_unique_id_configured()
                title = user_input.get(CONF_NAME) or (
                    entry.title if entry else f"Київ, черга {queue}"
                )
                if entry:
                    return self.async_update_reload_and_abort(
                        entry,
                        title=title,
                        unique_id=unique_id,
                        data={
                            **entry.data,
                            CONF_OPERATOR: operator,
                            "queue": queue,
                            CONF_ENTITY_UNIQUE_ID: entry.data.get(CONF_ENTITY_UNIQUE_ID)
                            or entry.unique_id
                            or entry.entry_id,
                        },
                        reason="reconfigure_successful",
                    )
                data = {CONF_OPERATOR: operator, "queue": queue}
                if any(
                    existing.data.get(CONF_ENTITY_UNIQUE_ID, existing.unique_id)
                    == unique_id
                    for existing in self._async_current_entries()
                ):
                    # Reconfiguration can retain an old queue's registry identity.
                    data[CONF_ENTITY_UNIQUE_ID] = f"{unique_id}_{uuid4().hex}"
                return self.async_create_entry(title=title, data=data)

        preferred_queue = entry.data["queue"] if entry else DEFAULT_QUEUE
        default_queue = (
            preferred_queue
            if preferred_queue in self._queues
            else (self._queues[0] if self._queues else preferred_queue)
        )
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME, default=entry.title if entry else "Alerts Energy"
                ): str,
                vol.Required("queue", default=default_queue): vol.In(self._queues)
                if self._queues
                else str,
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
