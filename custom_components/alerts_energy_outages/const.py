"""Constants for the Alerts Energy Outages integration."""

from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "alerts_energy_outages"

CONF_OPERATOR: Final = "operator"
DEFAULT_OPERATOR: Final = "kyiv_oblenergo"
DEFAULT_QUEUE: Final = "2.2"
CONF_ENTITY_UNIQUE_ID: Final = "entity_unique_id"
SCHEDULE_TIME_ZONE: Final = ZoneInfo("Europe/Kyiv")

API_URL: Final = "https://alerts.energy/api/v1/source-registry/areas/kyiv/shutdowns"
SCAN_INTERVAL_SECONDS: Final = 60
