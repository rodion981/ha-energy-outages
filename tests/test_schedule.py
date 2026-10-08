"""Half-hour, state length and day validity regressions."""

from datetime import UTC, datetime

import pytest

from custom_components.alerts_energy_outages.coordinator import (
    format_boundary,
    format_periods,
    outage_periods,
    schedule_day_status,
)


@pytest.mark.parametrize(
    "hours,expected",
    [
        ([0] * 24, []),
        ([1] * 24, [(0, 48)]),
        ([2] + [0] * 23, [(0, 1)]),
        ([3] + [0] * 23, [(1, 2)]),
        ([3, 2] + [0] * 22, [(1, 3)]),
        ([0] * 23 + [3], [(47, 48)]),
    ],
)
def test_periods(hours, expected):
    assert outage_periods(hours) == expected


@pytest.mark.parametrize(
    "hours", [[0] * 23, [4] * 24, [-1] * 24, [True] * 24, ["1"] * 24, [None] * 24]
)
def test_reject_invalid_codes(hours):
    with pytest.raises(ValueError):
        outage_periods(hours)


def test_state_length_and_full_periods():
    periods = outage_periods([2] * 24)
    assert len(periods) == 24
    assert len(format_periods(periods)) <= 255
    assert "… (+" in format_periods(periods)
    assert format_periods([(47, 48)]) == "23:30–24:00"
    assert format_boundary(48) == "24:00"
    assert format_periods([], "No outages") == "No outages"


@pytest.mark.parametrize(
    "value,expected",
    [
        ([], "unpublished"),
        (None, "unpublished"),
        ([0] * 23, "invalid"),
        ([4] * 24, "invalid"),
        ([True] * 24, "invalid"),
        (["1"] * 24, "invalid"),
    ],
)
def test_day_validity(schedule, value, expected):
    schedule["tomorrow"] = value
    assert schedule_day_status(schedule, "today") == "published"
    assert schedule_day_status(schedule, "tomorrow") == expected


def test_unknown_or_stale_date(schedule):
    schedule["todayDate"] = "2026-10-06"
    assert schedule_day_status(schedule, "today") == "stale"
    schedule.pop("todayDate")
    assert schedule_day_status(schedule, "today") == "stale"


@pytest.mark.parametrize("status", ["EmergencyShutdowns", "Unknown", None])
def test_unknown_source_status(schedule, status):
    schedule["todayStatus"] = status
    assert schedule_day_status(schedule, "today") == "unpublished"


def test_midnight_and_source_timezone(schedule, freezer):
    freezer.move_to(datetime(2026, 10, 7, 21, tzinfo=UTC))
    assert schedule_day_status(schedule, "today") == "stale"
    assert schedule_day_status(schedule, "tomorrow") == "stale"


def test_dst_day(schedule, freezer):
    freezer.move_to(datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
    schedule["todayDate"] = "2026-10-25"
    schedule["tomorrowDate"] = "2026-10-26"
    assert schedule_day_status(schedule, "today") == "published"
    freezer.move_to(datetime(2026, 10, 25, 1, 30, tzinfo=UTC))
    assert schedule_day_status(schedule, "today") == "published"


def test_missing_schedule():
    assert schedule_day_status(None, "today") == "not_found"
    assert schedule_day_status({"schedule_found": False}, "today") == "not_found"
