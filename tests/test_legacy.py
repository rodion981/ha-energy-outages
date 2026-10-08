"""Legacy package schema, IDs, completeness and unavailable data."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import jsonpath
import yaml
from homeassistant.components.template.config import async_validate_config
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component


def package():
    return yaml.safe_load(Path("includes/packages/energyua_22.yaml").read_text())


def sensor(key):
    return next(
        item for item in package()["template"][0]["sensor"] if item["unique_id"] == key
    )


async def test_modern_schema_preserves_ids(hass):
    config = package()
    validated = await async_validate_config(hass, {"template": config["template"]})
    assert len(validated["template"][0]["sensor"]) == 27
    assert "sensor" not in config
    assert "binary_sensor" not in config
    entities = config["template"][0]["sensor"] + config["template"][0]["binary_sensor"]
    assert len(entities) == 28
    assert all(item["name"] == item["unique_id"] for item in entities)
    assert len({item["unique_id"] for item in entities}) == 28


async def test_third_period_and_full_attributes(hass):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    # Current Kyiv time is 12:00. The third outage must be detected.
    hours = [0] * 24
    for hour in (2, 7, 12):
        hours[hour] = 1
    hass.states.async_set(
        "sensor.energyua_22_today_hours",
        str(hours),
        {"todayDate": "2026-10-07", "todayStatus": "ScheduleApplies"},
    )
    brief = sensor("energyua_22_today_brief")
    periods = Template(brief["attributes"]["periods"], hass).async_render()
    assert len(periods) == 3
    binary = package()["template"][0]["binary_sensor"][0]
    assert Template(binary["state"], hass).async_render() is True


async def test_missing_data_is_unavailable(hass):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    hass.states.async_set("sensor.energyua_22_today_hours", "unavailable")
    binary = package()["template"][0]["binary_sensor"][0]
    assert Template(binary["availability"], hass).async_render() is False
    assert (
        "Даних на сьогодні немає"
        in Template(sensor("energyua_22_today_brief")["state"], hass).async_render()
    )


async def test_all_periods_state_limit(hass):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    hass.states.async_set(
        "sensor.energyua_22_today_hours",
        str([2] * 24),
        {"todayDate": "2026-10-07", "todayStatus": "ScheduleApplies"},
    )
    brief = sensor("energyua_22_today_brief")
    assert len(Template(brief["state"], hass).async_render()) <= 255
    assert len(Template(brief["attributes"]["periods"], hass).async_render()) == 24


async def test_no_outages_is_a_published_tomorrow(hass):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    hass.states.async_set(
        "sensor.energyua_22_tomorrow_hours",
        str([0] * 24),
        {"tomorrowDate": "2026-10-08", "tomorrowStatus": "ScheduleApplies"},
    )
    assert (
        Template(sensor("energyua_22_tomorrow_fresh")["state"], hass).async_render()
        is True
    )


async def test_raw_response_date_status_and_codes(hass, schedule):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    raw = package()["rest"][0]["sensor"][0]["value_template"]
    template = Template(raw, hass)
    assert template.async_render({"value_json": [schedule]}) == schedule["today"]
    schedule["todayStatus"] = "EmergencyShutdowns"
    assert template.async_render({"value_json": [schedule]}) == "unknown"
    schedule["todayStatus"] = "ScheduleApplies"
    schedule["today"] = [True] * 24
    assert template.async_render({"value_json": [schedule]}) == "unknown"
    assert template.async_render({"value_json": []}) == "unknown"


def test_metadata_jsonpath_exact_match(schedule):
    other = deepcopy(schedule)
    other["initiator"] = "other"
    path = package()["rest"][0]["sensor"][0]["json_attributes_path"]
    parser = getattr(jsonpath, "search", None)
    result = (
        parser(path, [other, schedule])
        if parser
        else jsonpath.jsonpath([other, schedule], path)
    )
    assert result == [schedule]


async def test_legacy_midnight(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    hass.states.async_set(
        "sensor.energyua_22_today_hours",
        str([0] * 24),
        {"todayDate": "2026-10-07", "todayStatus": "ScheduleApplies"},
    )
    binary = package()["template"][0]["binary_sensor"][0]
    assert Template(binary["availability"], hass).async_render() is True
    freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
    assert Template(binary["availability"], hass).async_render() is False
    assert (
        "Даних на сьогодні немає"
        in Template(sensor("energyua_22_today_brief")["state"], hass).async_render()
    )


async def test_clean_template_setup(hass, caplog):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    hours = [0] * 24
    for hour in (2, 7, 12):
        hours[hour] = 1
    hass.states.async_set(
        "sensor.energyua_22_today_hours",
        json.dumps(hours),
        {"todayDate": "2026-10-07", "todayStatus": "ScheduleApplies"},
    )
    hass.states.async_set(
        "sensor.energyua_22_tomorrow_hours",
        json.dumps([0] * 24),
        {"tomorrowDate": "2026-10-08", "tomorrowStatus": "ScheduleApplies"},
    )
    assert await async_setup_component(
        hass, "template", {"template": package()["template"]}
    )
    await hass.async_block_till_done()
    entities = package()["template"][0]
    assert all(
        hass.states.get("sensor." + item["unique_id"]) for item in entities["sensor"]
    )
    assert hass.states.get("binary_sensor.energyua_22_outage_now").state == "on"
    assert (
        len(hass.states.get("sensor.energyua_22_today_brief").attributes["periods"])
        == 3
    )
    assert datetime.fromisoformat(
        hass.states.get("sensor.energyua_22_today_slot1_start").state
    ) == datetime(2026, 10, 6, 23, tzinfo=UTC)

    assert (
        hass.states.get("sensor.energyua_22_today_slot1_duration_h_text").state == "1.0"
    )
    assert not [record for record in caplog.records if record.levelname == "ERROR"]
    for platform in async_get_platforms(hass, "template"):
        await platform.async_reset()
