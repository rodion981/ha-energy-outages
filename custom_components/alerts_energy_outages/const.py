"""Constants for the Alerts Energy Outages integration."""

from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "alerts_energy_outages"

CONF_OPERATOR: Final = "operator"
CONF_AREA: Final = "area"
DEFAULT_AREA: Final = "kyiv"
DEFAULT_OPERATOR: Final = "kyiv_oblenergo"
DEFAULT_QUEUE: Final = "2.2"
CONF_ENTITY_UNIQUE_ID: Final = "entity_unique_id"
DATA_AREAS: Final = "_area_coordinators"
SCHEDULE_TIME_ZONE: Final = ZoneInfo("Europe/Kyiv")

SITE_URL: Final = "https://alerts.energy"
API_BASE_URL: Final = f"{SITE_URL}/api/v1"
API_URL: Final = f"{API_BASE_URL}/source-registry/areas/{DEFAULT_AREA}/shutdowns"
SCAN_INTERVAL_SECONDS: Final = 60
