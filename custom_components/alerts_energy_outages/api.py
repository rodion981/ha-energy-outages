"""Client for the public Alerts Energy schedule endpoint."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_URL


class AlertsEnergyApiError(Exception):
    """Raised when Alerts Energy cannot provide a valid schedule."""


class AlertsEnergyApi:
    """Small async client for Alerts Energy."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_get_schedules(self) -> list[dict[str, Any]]:
        """Return public schedules, rejecting malformed response rows."""
        try:
            async with self._session.get(
                API_URL,
                headers={
                    "Accept": "application/json",
                    "Referer": "https://alerts.energy/kyiv",
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

    async def async_get_queues(self, operator: str) -> list[str]:
        """Discover exact queue identifiers without guessing mappings."""
        rows = await self.async_get_schedules()
        return sorted(
            {
                row["queue"]
                for row in rows
                if row.get("initiator") == operator
                and isinstance(row.get("queue"), str)
                and row["queue"]
            }
        )

    async def async_get_schedule(self, operator: str, queue: str) -> dict[str, Any]:
        """Return one row; a missing queue remains explicitly unavailable."""
        payload = await self.async_get_schedules()

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
