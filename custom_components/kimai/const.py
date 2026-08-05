"""Constants for the Kimai integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "kimai"

CONF_API_TOKEN: Final = "api_token"
CONF_BASE_URL: Final = "base_url"
CONF_DEFAULT_ACTIVITY_ID: Final = "default_activity_id"
CONF_DEFAULT_PROJECT_ID: Final = "default_project_id"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=5)
PLATFORMS: Final = (Platform.SENSOR, Platform.CALENDAR)

SERVICE_LOG_TIME: Final = "log_time"
SERVICE_GET_DAY_HOURS: Final = "get_day_hours"
SERVICE_SET_DAY_HOURS: Final = "set_day_hours"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_PROJECT_ID: Final = "project_id"
ATTR_ACTIVITY_ID: Final = "activity_id"
ATTR_DATE: Final = "date"
ATTR_START_TIME: Final = "start_time"
ATTR_DURATION_HOURS: Final = "duration_hours"
ATTR_DESCRIPTION: Final = "description"
ATTR_BILLABLE: Final = "billable"
