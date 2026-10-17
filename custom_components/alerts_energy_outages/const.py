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
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL_MINUTES: Final = 15
MIN_SCAN_INTERVAL_MINUTES: Final = 1
MAX_SCAN_INTERVAL_MINUTES: Final = 1440
SCAN_INTERVAL_SECONDS: Final = DEFAULT_SCAN_INTERVAL_MINUTES * 60
