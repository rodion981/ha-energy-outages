"""Validate and combine planned and conditional source intervals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TypeGuard

from .const import SCHEDULE_TIME_ZONE

# Convert source codes to first/second-half bits before taking the union.
_MASKS = (0, 3, 1, 2)
_CODES = (0, 2, 3, 1)


def align_schedule_dates(data: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Select day fields by their source date without changing the cached row."""
    result = dict(data)
    today = now.astimezone(SCHEDULE_TIME_ZONE).date()
    for target in ("today", "tomorrow"):
        expected = (today + timedelta(days=target == "tomorrow")).isoformat()
        # Prefer the field of the requested day if both source dates match.
        # A malformed/empty authoritative day must never be hidden by a fallback.
        other = "tomorrow" if target == "today" else "today"
        source = next(
            (
                candidate
                for candidate in (target, other)
                if data.get(f"{candidate}Date") == expected
            ),
            target,
        )
        if source == target:
            continue
        for suffix in (
            "",
            "Date",
            "Status",
            "Possible",
            "_date",
            "_status",
            "_possible",
            "_checked_at",
            "_published_schedule",
        ):
            if f"{source}{suffix}" in data:
                result[f"{target}{suffix}"] = data[f"{source}{suffix}"]
            else:
                result.pop(f"{target}{suffix}", None)
        if target == "today":
            # The API supplies notices only for its original today, not tomorrow.
            result.pop("today_announcements", None)
    return result


def _valid_hours(value: object) -> TypeGuard[list[int]]:
    return (
        isinstance(value, list)
        and len(value) == 24
        and all(type(code) is int and code in range(4) for code in value)
    )


@dataclass(frozen=True, kw_only=True)
class DaySchedule:
    """Retain source certainty while computing a conservative planning union."""

    planned: list[int]
    possible: list[int]

    @property
    def combined(self) -> list[int]:
        return [
            _CODES[_MASKS[planned] | _MASKS[possible]]
            for planned, possible in zip(self.planned, self.possible, strict=True)
        ]

    def slot_type(self, boundary: int) -> str:
        """Let planned intervals take precedence where both arrays overlap."""
        mask = 1 if boundary % 2 == 0 else 2
        if _MASKS[self.planned[boundary // 2]] & mask:
            return "planned"
        if _MASKS[self.possible[boundary // 2]] & mask:
            return "possible"
        return "none"

    @property
    def outage_type(self) -> str:
        kinds = {self.slot_type(slot) for slot in range(48)} - {"none"}
        return "mixed" if len(kinds) > 1 else next(iter(kinds), "none")

    def as_dict(self) -> dict[str, list[int]]:
        return {"planned": self.planned.copy(), "possible": self.possible.copy()}


def normalize_day(data: dict[str, Any], day: str) -> DaySchedule:
    """Reject malformed present fields; absent/empty Possible adds no intervals."""
    planned = data.get(day)
    possible = data.get(f"{day}Possible", [])
    if not _valid_hours(planned) or not (
        isinstance(possible, list) and (not possible or _valid_hours(possible))
    ):
        raise ValueError("Expected 24 integer outage codes in the range 0..3")
    return DaySchedule(planned=planned.copy(), possible=possible.copy() or [0] * 24)
