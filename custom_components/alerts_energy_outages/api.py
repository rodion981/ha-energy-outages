"""Authenticated Alerts Energy client shared by the entire HA installation."""

from __future__ import annotations

import asyncio
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE_URL,
    DEFAULT_AREA,
    DOMAIN,
    MAX_RETRY_INTERVAL_SECONDS,
    RETRY_INTERVAL_SECONDS,
    SITE_URL,
)

STORAGE_KEY = f"{DOMAIN}.api"


async def async_get_api(hass: HomeAssistant) -> AlertsEnergyApi:
    """Load one durable identity/client, including simultaneous config flows."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    lock = domain_data.setdefault("_api_lock", asyncio.Lock())
    async with lock:
        if "_api" not in domain_data:
            store: Store[dict[str, Any]] = Store(hass, 1, STORAGE_KEY)
            loaded = await store.async_load()
            stored = loaded if isinstance(loaded, dict) else {}
            identity = stored.get("instance_id")
            try:
                if not isinstance(identity, str) or UUID(identity).version != 4:
                    raise ValueError
            except ValueError:
                identity = str(uuid4())
            api = AlertsEnergyApi(async_get_clientsession(hass), identity, store)
            api.restore(stored.get("requests"))
            # Save identity before sending any request.
            await api.async_save()
            domain_data["_api"] = api
        return domain_data["_api"]


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the entity contract stable across old/new upstream API versions."""
    result = dict(row)
    for old, new in (
        ("supplierName", "supplier_name"),
        ("areaSlug", "area_slug"),
        *(
            (f"{day}{suffix}", f"{day}_{suffix.lower()}")
            for day in ("today", "tomorrow")
            for suffix in ("Date", "Status", "Possible")
        ),
    ):
        # Presence, not truthiness: null/empty new fields must not revive old data.
        if new in row:
            result[old] = row[new]
    return result


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

    def __init__(
        self,
        message: str,
        *,
        reason: Literal["connection_error", "invalid"] = "connection_error",
        retry_after: float = RETRY_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.retry_after = retry_after


class AlertsEnergyApi:
    """Small async client for Alerts Energy."""

    def __init__(
        self,
        session: ClientSession,
        instance_id: str | None = None,
        store: Store[dict[str, Any]] | None = None,
    ) -> None:
        self._session = session
        self._instance_id = instance_id or str(uuid4())
        self._store = store
        self._requests: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._save_lock = asyncio.Lock()

    def restore(self, stored: Any) -> None:
        """Restore bounded request state; corrupted entries never become data."""
        if not isinstance(stored, dict):
            return
        for path, state in stored.items():
            if (
                not isinstance(path, str)
                or not path.startswith("source-registry/areas/")
                or not path.endswith("/shutdowns")
                or not isinstance(state, dict)
            ):
                continue
            try:
                next_request = float(state["next_request"])
                failures = int(state.get("failures", 0))
                fetched_at = float(state.get("fetched_at", 0))
                if not all(
                    0 <= value < datetime.max.replace(tzinfo=UTC).timestamp()
                    for value in (next_request, fetched_at)
                ):
                    continue
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            rows = state.get("rows")
            self._requests[path] = {
                "next_request": next_request,
                "failures": max(0, min(failures, 8)),
                "fetched_at": fetched_at,
                "reason": "invalid"
                if state.get("reason") == "invalid"
                else "connection_error",
                "failed": bool(state.get("failed", True)),
            }
            if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                self._requests[path]["rows"] = rows

    async def async_save(self) -> None:
        """Serialize shared regional state without persisting credentials."""
        if self._store is not None:
            async with self._save_lock:
                try:
                    await self._store.async_save(
                        {
                            "instance_id": self._instance_id,
                            "requests": deepcopy(
                                {
                                    path: state
                                    for path, state in self._requests.items()
                                    if path.endswith("/shutdowns")
                                }
                            ),
                        }
                    )
                except OSError:
                    raise AlertsEnergyApiError(
                        "Cannot persist Alerts Energy API state"
                    ) from None

    @staticmethod
    def _schedule_path(area: str) -> str:
        return f"source-registry/areas/{quote(area, safe='')}/shutdowns"

    def cached_schedule(
        self, area: str
    ) -> tuple[list[dict[str, Any]], datetime] | None:
        """Return the latest response and its real receipt time, even after error."""
        state = self._requests.get(self._schedule_path(area), {})
        if "rows" not in state or not state.get("fetched_at"):
            return None
        return deepcopy(state["rows"]), datetime.fromtimestamp(state["fetched_at"], UTC)

    def retry_delay(self, area: str) -> float:
        """Expose the shared server/local deadline to the regional timer."""
        state = self._requests.get(self._schedule_path(area), {})
        return max(0.0, state.get("next_request", 0) - dt_util.utcnow().timestamp())

    @staticmethod
    def _retry_after(value: str | None) -> float:
        """Support both standard Retry-After formats; never retry too early."""
        try:
            if value is None:
                return 0
            if value.strip().isdigit():
                seconds = float(value)
                return seconds if math.isfinite(seconds) and seconds < 1e10 else 0
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=UTC)
            return max(0, (target - dt_util.utcnow()).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0

    async def _async_get_rows(self, path: str) -> list[dict[str, Any]]:
        """Coalesce callers and enforce area quotas for flows, reload and polling."""
        async with self._locks.setdefault(path, asyncio.Lock()):
            state = self._requests.setdefault(path, {})
            now = dt_util.utcnow().timestamp()
            remaining = state.get("next_request", 0) - now
            if remaining > 0:
                if state.get("failed", True) or "rows" not in state:
                    raise AlertsEnergyApiError(
                        "API request deferred until the allowed retry time",
                        reason=state.get("reason", "connection_error"),
                        retry_after=remaining,
                    )
                return deepcopy(state["rows"])
            # Record the attempt durably before network IO, including cancellation.
            state.update(
                next_request=now + RETRY_INTERVAL_SECONDS,
                failed=True,
                reason="connection_error",
            )
            await self.async_save()
            try:
                rows = await self._async_fetch_rows(path)
            except AlertsEnergyApiError as err:
                failures = min(state.get("failures", 0) + 1, 8)
                delay = max(
                    min(
                        RETRY_INTERVAL_SECONDS * 2 ** (failures - 1),
                        MAX_RETRY_INTERVAL_SECONDS,
                    ),
                    err.retry_after,
                )
                state.update(
                    failures=failures,
                    reason=err.reason,
                    next_request=dt_util.utcnow().timestamp() + delay,
                )
                await self.async_save()
                raise AlertsEnergyApiError(
                    str(err), reason=err.reason, retry_after=delay
                ) from None
            state.update(
                rows=rows,
                fetched_at=dt_util.utcnow().timestamp(),
                failed=False,
                failures=0,
                next_request=dt_util.utcnow().timestamp() + RETRY_INTERVAL_SECONDS,
            )
            await self.async_save()
            return deepcopy(rows)

    async def _async_fetch_rows(self, path: str) -> list[dict[str, Any]]:
        """Read a list with safe errors: never include headers, body or credentials."""
        from .credentials import API_KEY

        try:
            async with self._session.get(
                f"{API_BASE_URL}/{path}",
                headers={
                    "Accept": "application/json",
                    "Referer": SITE_URL,
                    "Authorization": f"Bearer {API_KEY}",
                    "X-HA-Instance-ID": self._instance_id,
                },
                allow_redirects=False,
                timeout=ClientTimeout(total=30),
            ) as response:
                if response.status >= 300:
                    raise AlertsEnergyApiError(
                        f"Alerts Energy API returned HTTP {response.status}",
                        retry_after=self._retry_after(
                            response.headers.get("Retry-After")
                        ),
                    )
                payload = await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise AlertsEnergyApiError(
                "Alerts Energy API returned invalid JSON"
                if isinstance(err, (ValueError, ContentTypeError))
                else "Cannot connect to Alerts Energy API",
                reason="invalid"
                if isinstance(err, (ValueError, ContentTypeError))
                else "connection_error",
            ) from None

        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise AlertsEnergyApiError("Unexpected response format", reason="invalid")
        return [normalize_row(row) for row in payload]

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
        return await self._async_get_rows(self._schedule_path(area))

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
