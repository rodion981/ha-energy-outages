"""Validate source check times and advisory emergency announcements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import SCHEDULE_TIME_ZONE


def source_timestamp(value: Any) -> datetime | None:
    """Accept only explicit, timezone-aware source timestamps."""
    if not isinstance(value, str):
        return None
    try:
        parsed = dt_util.parse_datetime(value)
        if parsed is None or parsed.tzinfo is None:
            return None
        return dt_util.as_utc(parsed)
    except (ValueError, OverflowError):
        return None


def _current_day(data: dict[str, Any], day: str, now: datetime) -> bool:
    expected = now.astimezone(SCHEDULE_TIME_ZONE).date() + timedelta(
        days=day == "tomorrow"
    )
    return (
        data.get("schedule_found", True)
        and data.get(f"{day}Date") == expected.isoformat()
    )


def source_checked_at(
    data: dict[str, Any], day: str, now: datetime | None = None
) -> datetime | None:
    """Keep source verification separate from API receipt and publication."""
    if not _current_day(data, day, now or dt_util.utcnow()):
        return None
    return source_timestamp(data.get(f"{day}_checked_at"))


@dataclass(frozen=True)
class EmergencyNotices:
    """Current advisory messages and their next local clock transitions."""

    warning: bool | None = None
    notices: tuple[dict[str, Any], ...] = ()
    boundaries: tuple[datetime, ...] = ()


def emergency_notices(
    data: dict[str, Any], now: datetime | None = None
) -> EmergencyNotices:
    """Never interpret a scoped announcement as an address-level power state."""
    now = now or dt_util.utcnow()
    raw = data.get("today_announcements")
    if not _current_day(data, "today", now) or not isinstance(raw, list):
        return EmergencyNotices()
    notices: list[dict[str, Any]] = []
    boundaries: set[datetime] = set()
    invalid = False
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            invalid = True
            continue
        if item["kind"] != "Emergency":
            continue
        state, scope = item.get("state"), item.get("scope")
        if state == "cancelled":
            continue
        if state not in ("active", "possible") or scope not in (
            "supplier",
            "local",
            "regional",
        ):
            invalid = True
            continue
        timestamps = {
            key: source_timestamp(item[key])
            for key in ("published_at", "effective_at", "expires_at")
            if key in item
        }
        if any(value is None for value in timestamps.values()):
            invalid = True
            continue
        start = timestamps.get("effective_at") or timestamps.get("published_at")
        end = timestamps.get("expires_at")
        if start is not None and end is not None and end <= start:
            invalid = True
            continue
        if end is not None and end <= now:
            continue
        boundaries.update(value for value in (start, end) if value and value > now)
        if start is not None and start > now:
            continue
        notices.append(
            {
                "kind": "Emergency",
                "state": state,
                "scope": scope,
                **{
                    key: value.isoformat()
                    for key, value in timestamps.items()
                    if value is not None
                },
            }
        )
    return EmergencyNotices(
        warning=True if notices else None if invalid else False,
        notices=tuple(notices),
        boundaries=tuple(sorted(boundaries)),
    )
