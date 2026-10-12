"""Published horizons, exact transitions and DST-aware outage forecasts."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from custom_components.alerts_energy_outages.forecast import schedule_forecast


def forecast_data(schedule, day="2026-10-07", tomorrow="2026-10-08"):
    data = deepcopy(schedule)
    data.update(today=[0] * 24, tomorrow=[0] * 24, todayDate=day, tomorrowDate=tomorrow)
    return data


def test_next_and_current_are_distinct(schedule):
    data = forecast_data(schedule)
    data["today"][12] = 2
    data["today"][16] = 1
    now = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
    result = schedule_forecast(data, now)
    assert result.context == "current"
    assert result.selected.start == now
    assert result.selected.end == datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
    assert result.selected.duration_minutes == 30
    assert result.next_outage.start == datetime(2026, 10, 7, 13, tzinfo=UTC)
    after = schedule_forecast(data, datetime(2026, 10, 7, 9, 30, tzinfo=UTC))
    assert after.context == "next"
    assert after.selected == after.next_outage
    assert after.selected.duration_minutes == 60


def test_third_period_and_half_hour_codes(schedule):
    data = forecast_data(schedule)
    data["today"][2] = 1
    data["today"][7] = 1
    data["today"][12] = 3
    result = schedule_forecast(data, datetime(2026, 10, 7, 9, tzinfo=UTC))
    assert result.next_outage.start == datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
    assert result.selected.end == datetime(2026, 10, 7, 10, tzinfo=UTC)
    assert result.selected.duration_minutes == 30


def test_no_outages_in_published_horizon(schedule):
    result = schedule_forecast(
        forecast_data(schedule), datetime(2026, 10, 7, 9, tzinfo=UTC)
    )
    assert result.selected is None
    assert result.next_outage is None
    assert result.context == "none"
    assert result.coverage_end == datetime(2026, 10, 8, 21, tzinfo=UTC)


def test_midnight_is_not_an_invented_restoration(schedule):
    data = forecast_data(schedule)
    data["today"][23] = 1
    data["tomorrow"] = []
    result = schedule_forecast(data, datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    assert result.context == "current"
    assert result.selected.end is None
    assert result.selected.duration_minutes is None
    assert result.coverage_end == datetime(2026, 10, 7, 21, tzinfo=UTC)


def test_continuous_outage_merges_across_midnight(schedule):
    data = forecast_data(schedule)
    data["today"][23] = 1
    data["tomorrow"][0] = 1
    result = schedule_forecast(data, datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    assert result.selected.start == datetime(2026, 10, 7, 20, tzinfo=UTC)
    assert result.selected.end == datetime(2026, 10, 7, 22, tzinfo=UTC)
    assert result.selected.duration_minutes == 120
    assert result.next_outage is None


def test_published_zero_at_midnight_confirms_restoration(schedule):
    data = forecast_data(schedule)
    data["today"][23] = 1
    result = schedule_forecast(data, datetime(2026, 10, 7, 20, 15, tzinfo=UTC))
    assert result.selected.end == datetime(2026, 10, 7, 21, tzinfo=UTC)
    assert result.selected.duration_minutes == 60


def test_end_of_tomorrow_is_outside_published_horizon(schedule):
    data = forecast_data(schedule)
    data["tomorrow"][23] = 1
    result = schedule_forecast(data, datetime(2026, 10, 7, 9, tzinfo=UTC))
    assert result.context == "next"
    assert result.selected.start == datetime(2026, 10, 8, 20, tzinfo=UTC)
    assert result.selected.end is None


@pytest.mark.parametrize("status", ["invalid", "stale", "unpublished", "missing"])
def test_unknown_today_never_assumes_a_current_state(schedule, status):
    data = forecast_data(schedule)
    data["tomorrow"][12] = 1
    if status == "invalid":
        data["today"] = [9] * 24
    elif status == "stale":
        data["todayDate"] = "2026-10-06"
    elif status == "unpublished":
        data["today"] = []
    else:
        data["schedule_found"] = False
    result = schedule_forecast(data, datetime(2026, 10, 7, 9, tzinfo=UTC))
    assert result.selected is None
    assert result.coverage_end is None


def test_dst_fall_repeated_hour_has_real_two_hour_duration(schedule):
    data = forecast_data(schedule, "2026-10-25", "2026-10-26")
    data["today"][3] = 1
    result = schedule_forecast(data, datetime(2026, 10, 25, 0, 15, tzinfo=UTC))
    assert result.selected.start == datetime(2026, 10, 25, 0, tzinfo=UTC)
    assert result.selected.end == datetime(2026, 10, 25, 2, tzinfo=UTC)
    assert result.selected.duration_minutes == 120


def test_dst_spring_skips_nonexistent_hour(schedule):
    data = forecast_data(schedule, "2026-03-29", "2026-03-30")
    data["today"][3] = 1
    result = schedule_forecast(data, datetime(2026, 3, 28, 22, tzinfo=UTC))
    assert result.selected is None
    data["today"][1:5] = [1] * 4
    result = schedule_forecast(data, datetime(2026, 3, 28, 22, tzinfo=UTC))
    assert result.selected.duration_minutes == 180


def test_current_outage_at_start_of_coverage_has_unknown_full_duration(schedule):
    data = forecast_data(schedule)
    data["today"][0] = 1
    result = schedule_forecast(data, datetime(2026, 10, 6, 21, 15, tzinfo=UTC))
    assert result.context == "current"
    assert not result.selected.start_known
    assert result.selected.end == datetime(2026, 10, 6, 22, tzinfo=UTC)
    assert result.selected.duration_minutes is None


def test_tomorrow_midnight_start_is_known_when_today_ends_with_power(schedule):
    data = forecast_data(schedule)
    data["tomorrow"][0] = 1
    result = schedule_forecast(data, datetime(2026, 10, 7, 9, tzinfo=UTC))
    assert result.next_outage.start == datetime(2026, 10, 7, 21, tzinfo=UTC)
    assert result.selected.start_known
    assert result.selected.duration_minutes == 60


def test_source_timezone_does_not_depend_on_callers_timezone(schedule):
    from zoneinfo import ZoneInfo

    data = forecast_data(schedule)
    data["today"][12] = 2
    now = datetime(2026, 10, 7, 5, tzinfo=ZoneInfo("America/New_York"))
    assert schedule_forecast(data, now).selected.start == datetime(
        2026, 10, 7, 9, tzinfo=UTC
    )
