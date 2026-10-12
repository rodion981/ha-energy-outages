"""Client for the public Alerts Energy schedule endpoint."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE_URL, DEFAULT_AREA, SITE_URL


@dataclass(frozen=True, kw_only=True)
class Territory:
    """A public administrative unit from the Alerts Energy directory."""

    katottg: str
    slug: str
    name: str
    category: str
    level: int


class AlertsEnergyApiError(Exception):
    """Raised when Alerts Energy cannot provide a valid schedule."""


class AlertsEnergyApi:
    """Small async client for Alerts Energy."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def _async_get_rows(self, path: str) -> list[dict[str, Any]]:
        """Read a public list without accepting malformed rows."""
        try:
            async with self._session.get(
                f"{API_BASE_URL}/{path}",
                headers={
                    "Accept": "application/json",
                    "Referer": SITE_URL,
                },
                timeout=ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise AlertsEnergyApiError(str(err)) from err

        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise AlertsEnergyApiError("Unexpected response format")
        return payload

    async def _async_get_territories(self, parent: str | None) -> list[Territory]:
        """Validate directory records and their parent before offering choices."""
        path = "atus" if parent is None else f"atus/{quote(parent, safe='')}"
        rows = await self._async_get_rows(path)
        result = []
        for row in rows:
            if (
                not isinstance(row.get("katottg"), str)
                or not re.fullmatch(r"UA\d{17}", row["katottg"])
                or not isinstance(row.get("slug"), str)
                or not re.fullmatch(r"[a-z0-9-]+", row["slug"])
                or not isinstance(row.get("name"), str)
                or not row["name"].strip()
                or type(row.get("level")) is not int
                or row["level"] not in range(1, 6)
                or not isinstance(row.get("category"), str)
                or row.get("parent_katottg") != parent
            ):
                raise AlertsEnergyApiError("Unexpected territory format")
            # Some village full_name values incorrectly say 'city' in the source.
            name = row.get("full_name") if row["level"] < 4 else row["name"]
            result.append(
                Territory(
                    katottg=row["katottg"],
                    slug=row["slug"],
                    name=name if isinstance(name, str) and name else row["name"],
                    category=row["category"],
                    level=row["level"],
                )
            )
        if len({item.katottg for item in result}) != len(result):
            raise AlertsEnergyApiError("Duplicate territory identifiers")
        return sorted(result, key=lambda item: item.name)

    async def async_get_areas(self) -> list[Territory]:
        """Discover oblasts and cities with special status."""
        return await self._async_get_territories(None)

    async def async_get_children(self, parent: str) -> list[Territory]:
        """Discover districts, communities or settlements below one unit."""
        return await self._async_get_territories(parent)

    async def async_get_operators(self, area: str) -> dict[str, str]:
        """Return exact operator identifiers and public display names."""
        rows = await self._async_get_rows(
            f"source-registry/areas/{quote(area, safe='')}/suppliers"
        )
        operators = {}
        for row in rows:
            if (
                row.get("areaSlug") != area
                or not isinstance(row.get("slug"), str)
                or not row["slug"]
                or not isinstance(row.get("supplierName"), str)
                or not row["supplierName"]
                or row["slug"] in operators
            ):
                raise AlertsEnergyApiError("Unexpected operator format")
            operators[row["slug"]] = row["supplierName"]
        return operators

    async def async_get_schedules(
        self, area: str = DEFAULT_AREA
    ) -> list[dict[str, Any]]:
        """Return the selected area's schedules, preserving the Kyiv default."""
        return await self._async_get_rows(
            f"source-registry/areas/{quote(area, safe='')}/shutdowns"
        )

    async def async_get_queues(
        self, operator: str, area: str = DEFAULT_AREA
    ) -> list[str]:
        """Discover exact queue identifiers without guessing mappings."""
        rows = await self.async_get_schedules(area)
        return sorted(
            {
                row["queue"]
                for row in rows
                if row.get("initiator") == operator
                and isinstance(row.get("queue"), str)
                and row["queue"]
            }
        )

    async def async_get_schedule(
        self, operator: str, queue: str, area: str = DEFAULT_AREA
    ) -> dict[str, Any]:
        """Return one row; a missing queue remains explicitly unavailable."""
        payload = await self.async_get_schedules(area)
        return self.select_schedule(payload, operator, queue)

    @staticmethod
    def select_schedule(
        payload: list[dict[str, Any]], operator: str, queue: str
    ) -> dict[str, Any]:
        """Select the same exact row from an already fetched regional response."""

        row = next(
            (
                item
                for item in payload
                if item.get("initiator") == operator and item.get("queue") == queue
            ),
            None,
        )
        if row is None:
            return {"initiator": operator, "queue": queue, "schedule_found": False}
        row = dict(row)
        row["schedule_found"] = True
        return row
