"""Select an area, settlement, operator and exact outage queue."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorMode,
)

from .api import AlertsEnergyApi, AlertsEnergyApiError, Territory, async_get_api
from .const import (
    CONF_AREA,
    CONF_ENTITY_UNIQUE_ID,
    CONF_OPERATOR,
    CONF_SCAN_INTERVAL,
    DEFAULT_AREA,
    DEFAULT_QUEUE,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    SITE_URL,
)

SKIP_LOCALITY = "__skip__"
PREVIOUS_LOCALITY = "__back__"
RETRY_LOCALITY = "__retry__"


def select(choices: dict[str, str]) -> SelectSelector:
    """Use searchable labels while storing exact source identifiers."""
    return SelectSelector(
        {
            "options": [
                {"value": key, "label": label} for key, label in choices.items()
            ],
            "mode": SelectSelectorMode.DROPDOWN,
        }
    )


# HA's dynamic registration is covered by config flow runtime tests.
class AlertsEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Configure regional schedules without replacing existing entities."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._entry: ConfigEntry | None = None
        self._selection: dict[str, Any] = {}
        self._parents: list[Territory] = []
        self._queues: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AlertsEnergyOptionsFlow:
        """Offer polling options without repeating regional setup."""
        return AlertsEnergyOptionsFlow(config_entry)

    async def _async_api(self) -> AlertsEnergyApi:
        return await async_get_api(self.hass)

    def _retry_schema(self, back_label: str) -> vol.Schema:
        """Offer retry or return to a working choice when a source has no data."""
        return vol.Schema(
            {
                vol.Required("action", default="retry"): select(
                    {
                        "retry": "Повторити"
                        if self.hass.config.language == "uk"
                        else "Retry",
                        "back": back_label,
                    }
                )
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start a new configuration with the public regional directory."""
        return await self._async_area("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start reconfiguration while leaving the current entry operational."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if self._entry is None or self._entry.domain != DOMAIN:
            return self.async_abort(reason="invalid_entry")
        return await self._async_area("reconfigure", user_input)

    async def _async_area(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        areas: dict[str, Territory] = {}
        try:
            api = await self._async_api()
            areas = {item.slug: item for item in await api.async_get_areas()}
        except AlertsEnergyApiError:
            errors["base"] = "cannot_connect"
        else:
            if not areas:
                errors["base"] = "no_areas"
        if user_input is not None and CONF_AREA in user_input and not errors:
            area = areas.get(user_input.get(CONF_AREA, ""))
            if area is None:
                errors[CONF_AREA] = "invalid_selection"
            else:
                self._selection = {
                    CONF_AREA: area.slug,
                    "area_name": area.name,
                    "locality_id": None,
                    "locality_name": None,
                }
                self._parents = [area]
                # Kyiv and Sevastopol are themselves cities, not oblasts.
                if area.category == "K":
                    self._selection.update(
                        locality_id=area.katottg, locality_name=area.name
                    )
                    return await self.async_step_operator()
                return await self.async_step_locality()
        preferred = (
            self._entry.data.get(CONF_AREA, DEFAULT_AREA)
            if self._entry
            else DEFAULT_AREA
        )
        choices = {key: area.name for key, area in areas.items()}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_AREA,
                    default=preferred if preferred in areas else next(iter(areas), ""),
                ): select(choices)
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema if choices else vol.Schema({}),
            errors=errors,
            description_placeholders={"source_url": SITE_URL},
        )

    async def async_step_locality(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Walk the directory one district/community at a time, with no bulk crawl."""
        errors: dict[str, str] = {}
        parent = self._parents[-1]
        children: dict[str, Territory] = {}
        try:
            api = await self._async_api()
            children = {
                item.katottg: item
                for item in await api.async_get_children(parent.katottg)
            }
        except AlertsEnergyApiError:
            errors["base"] = "cannot_connect"
        else:
            if not children:
                errors["base"] = "no_localities"
        if user_input is not None:
            selected = user_input.get("locality", "")
            if selected == SKIP_LOCALITY:
                return await self.async_step_operator()
            if selected == PREVIOUS_LOCALITY and len(self._parents) > 1:
                self._parents.pop()
                return await self.async_step_locality()
            if not errors and selected != RETRY_LOCALITY:
                child = children.get(selected)
                if child is None or child.level <= parent.level:
                    errors["locality"] = "invalid_selection"
                elif child.level >= 4:
                    self._selection.update(
                        locality_id=child.katottg, locality_name=child.name
                    )
                    return await self.async_step_operator()
                else:
                    self._parents.append(child)
                    return await self.async_step_locality()
        ukrainian = self.hass.config.language == "uk"
        choices = {
            SKIP_LOCALITY: "Без вибору міста: графік області"
            if ukrainian
            else "Skip city: regional schedule"
        }
        if len(self._parents) > 1:
            choices[PREVIOUS_LOCALITY] = "Назад" if ukrainian else "Back"
        if errors:
            choices[RETRY_LOCALITY] = (
                "Повторити завантаження" if ukrainian else "Retry loading"
            )
        choices.update({key: child.name for key, child in children.items()})
        return self.async_show_form(
            step_id="locality",
            data_schema=vol.Schema({vol.Required("locality"): select(choices)}),
            errors=errors,
            description_placeholders={"territory": parent.name},
        )

    async def async_step_operator(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the actual supplier for the chosen area."""
        if user_input and user_input.get("action") == "back":
            return await self._async_area(
                "reconfigure" if self._entry else "user", None
            )
        errors: dict[str, str] = {}
        operators: dict[str, str] = {}
        try:
            api = await self._async_api()
            operators = await api.async_get_operators(self._selection[CONF_AREA])
        except AlertsEnergyApiError:
            errors["base"] = "cannot_connect"
        else:
            if not operators:
                errors["base"] = "no_operators"
        if user_input is not None and CONF_OPERATOR in user_input and not errors:
            operator = user_input.get(CONF_OPERATOR)
            if operator not in operators:
                errors[CONF_OPERATOR] = "invalid_selection"
            else:
                self._selection.update(
                    operator=operator, operator_name=operators[operator]
                )
                return await self.async_step_queue()
        preferred = self._entry.data.get(CONF_OPERATOR) if self._entry else None
        return self.async_show_form(
            step_id="operator",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OPERATOR,
                        default=preferred
                        if preferred in operators
                        else next(iter(operators), ""),
                    ): select(operators)
                }
            )
            if operators
            else self._retry_schema(
                "Обрати іншу область"
                if self.hass.config.language == "uk"
                else "Choose another region"
            ),
            errors=errors,
            description_placeholders={"area": self._selection["area_name"]},
        )

    async def async_step_queue(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the exact area/operator/queue before applying any changes."""
        if user_input and user_input.get("action") == "back":
            return await self.async_step_operator()
        errors: dict[str, str] = {}
        area = self._selection[CONF_AREA]
        operator = self._selection[CONF_OPERATOR]
        self._queues = []
        try:
            api = await self._async_api()
            self._queues = await api.async_get_queues(operator, area)
        except AlertsEnergyApiError:
            errors["base"] = "cannot_connect"
        else:
            if not self._queues:
                errors["base"] = "no_queues"
        if user_input is not None and "queue" in user_input and not errors:
            queue = user_input.get("queue")
            if queue not in self._queues:
                errors["queue"] = "invalid_queue"
            else:
                # Preserve the historical Kyiv identity and qualify other areas.
                unique_id = (
                    f"{operator}_{queue}"
                    if area == DEFAULT_AREA
                    else f"{area}_{operator}_{queue}"
                )
                await self.async_set_unique_id(unique_id)
                if self._entry is None or unique_id != self._entry.unique_id:
                    self._abort_if_unique_id_configured()
                data = {**self._selection, "queue": queue}
                title = user_input.get(CONF_NAME) or (
                    self._entry.title
                    if self._entry
                    else self._selection["locality_name"]
                    or self._selection["area_name"]
                )
                if self._entry:
                    data[CONF_ENTITY_UNIQUE_ID] = (
                        self._entry.data.get(CONF_ENTITY_UNIQUE_ID)
                        or self._entry.unique_id
                        or self._entry.entry_id
                    )
                    return self.async_update_reload_and_abort(
                        self._entry,
                        title=title,
                        unique_id=unique_id,
                        data={**self._entry.data, **data},
                        reason="reconfigure_successful",
                    )
                if any(
                    (
                        existing.data.get(CONF_ENTITY_UNIQUE_ID)
                        or existing.unique_id
                        or existing.entry_id
                    )
                    == unique_id
                    for existing in self._async_current_entries()
                ):
                    data[CONF_ENTITY_UNIQUE_ID] = f"{unique_id}_{uuid4().hex}"
                return self.async_create_entry(title=title, data=data)
        preferred = self._entry.data["queue"] if self._entry else DEFAULT_QUEUE
        default_queue = (
            preferred
            if preferred in self._queues
            else (self._queues[0] if self._queues else preferred)
        )
        return self.async_show_form(
            step_id="queue",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=self._entry.title
                        if self._entry
                        else self._selection["locality_name"]
                        or self._selection["area_name"],
                    ): str,
                    vol.Required("queue", default=default_queue): select(
                        {queue: queue for queue in self._queues}
                    ),
                }
            )
            if self._queues
            else self._retry_schema(
                "Обрати іншого оператора"
                if self.hass.config.language == "uk"
                else "Choose another operator"
            ),
            errors=errors,
            description_placeholders={"operator": self._selection["operator_name"]},
        )


class AlertsEnergyOptionsFlow(config_entries.OptionsFlow):
    """Configure the entry's requested polling interval."""

    def __init__(self, entry: ConfigEntry) -> None:
        # Keep HA 2024.6 compatibility without assigning modern config_entry.
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store whole minutes and preserve any other entry options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            minutes = user_input.get(CONF_SCAN_INTERVAL)
            if (
                isinstance(minutes, (int, float))
                and not isinstance(minutes, bool)
                and MIN_SCAN_INTERVAL_MINUTES <= minutes <= MAX_SCAN_INTERVAL_MINUTES
                and minutes == int(minutes)
            ):
                return self.async_create_entry(
                    title="",
                    data={**self._entry.options, CONF_SCAN_INTERVAL: int(minutes)},
                )
            errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=max(
                            MIN_SCAN_INTERVAL_MINUTES,
                            self._entry.options.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                            ),
                        ),
                    ): NumberSelector(
                        {
                            "min": MIN_SCAN_INTERVAL_MINUTES,
                            "max": MAX_SCAN_INTERVAL_MINUTES,
                            "step": 1,
                            "mode": NumberSelectorMode.BOX,
                            "unit_of_measurement": "min",
                        }
                    )
                }
            ),
            errors=errors,
            description_placeholders={"source_url": SITE_URL},
        )
