"""Home Assistant actions exposed by the Kimai integration."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ACTIVITY_ID,
    ATTR_BILLABLE,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_DESCRIPTION,
    ATTR_DURATION_HOURS,
    ATTR_PROJECT_ID,
    ATTR_START_TIME,
    CONF_DEFAULT_ACTIVITY_ID,
    CONF_DEFAULT_PROJECT_ID,
    DOMAIN,
    SERVICE_GET_DAY_HOURS,
    SERVICE_LOG_TIME,
    SERVICE_SET_DAY_HOURS,
)
from .coordinator import KimaiConfigEntry
from .models import KimaiTimesheet

ENTRY_FIELD = vol.Optional(ATTR_CONFIG_ENTRY_ID)
PROJECT_FIELD = vol.Optional(ATTR_PROJECT_ID)
ACTIVITY_FIELD = vol.Optional(ATTR_ACTIVITY_ID)
DATE_FIELD = vol.Required(ATTR_DATE)
START_FIELD = vol.Optional(ATTR_START_TIME, default=time(9))
DURATION_FIELD = vol.Required(ATTR_DURATION_HOURS)
DESCRIPTION_FIELD = vol.Optional(ATTR_DESCRIPTION, default="")
BILLABLE_FIELD = vol.Optional(ATTR_BILLABLE, default=True)

BASE_SERVICE_SCHEMA = vol.Schema(
    {
        ENTRY_FIELD: cv.string,
        PROJECT_FIELD: vol.All(vol.Coerce(int), vol.Range(min=1)),
        ACTIVITY_FIELD: vol.All(vol.Coerce(int), vol.Range(min=1)),
        DATE_FIELD: cv.date,
        START_FIELD: cv.time,
        DURATION_FIELD: vol.All(vol.Coerce(float), vol.Range(min=1 / 60, max=24)),
        DESCRIPTION_FIELD: cv.string,
        BILLABLE_FIELD: cv.boolean,
    }
)

GET_DAY_HOURS_SCHEMA = vol.Schema(
    {
        ENTRY_FIELD: cv.string,
        PROJECT_FIELD: vol.All(vol.Coerce(int), vol.Range(min=1)),
        ACTIVITY_FIELD: vol.All(vol.Coerce(int), vol.Range(min=1)),
        DATE_FIELD: cv.date,
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Kimai actions once for the integration domain."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_TIME):
        return

    async def async_handle_log_time(call: ServiceCall) -> dict[str, Any]:
        entry = _resolve_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        project_id, activity_id = _resolve_project_activity(entry, call.data)
        begin, end = _time_range(call.data)
        result = await entry.runtime_data.client.async_create_timesheet(
            project_id=project_id,
            activity_id=activity_id,
            begin=begin,
            end=end,
            description=call.data[ATTR_DESCRIPTION],
            billable=call.data[ATTR_BILLABLE],
        )
        await entry.runtime_data.coordinator.async_request_refresh()
        return {
            CONF_ID: result.id,
            "action": "created",
            ATTR_DURATION_HOURS: result.hours,
        }

    async def async_handle_set_day_hours(call: ServiceCall) -> dict[str, Any]:
        entry = _resolve_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        project_id, activity_id = _resolve_project_activity(entry, call.data)
        begin, end = _time_range(call.data)
        matching = await _async_matching_timesheets(
            entry,
            call.data[ATTR_DATE],
            project_id,
            activity_id,
        )
        if len(matching) > 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="multiple_matching_timesheets",
                translation_placeholders={"count": str(len(matching))},
            )

        if matching:
            previous = matching[0]
            result = await entry.runtime_data.client.async_update_timesheet(
                previous.id,
                project_id=project_id,
                activity_id=activity_id,
                begin=begin,
                end=end,
                description=call.data[ATTR_DESCRIPTION] or previous.description,
                billable=call.data[ATTR_BILLABLE],
            )
            action = "updated"
            previous_hours = previous.hours
        else:
            result = await entry.runtime_data.client.async_create_timesheet(
                project_id=project_id,
                activity_id=activity_id,
                begin=begin,
                end=end,
                description=call.data[ATTR_DESCRIPTION],
                billable=call.data[ATTR_BILLABLE],
            )
            action = "created"
            previous_hours = 0.0

        await entry.runtime_data.coordinator.async_request_refresh()
        return {
            CONF_ID: result.id,
            "action": action,
            "previous_hours": previous_hours,
            ATTR_DURATION_HOURS: result.hours,
        }

    async def async_handle_get_day_hours(call: ServiceCall) -> dict[str, Any]:
        entry = _resolve_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        project_id, activity_id = _resolve_project_activity(entry, call.data)
        matching = await _async_matching_timesheets(
            entry,
            call.data[ATTR_DATE],
            project_id,
            activity_id,
        )
        return {
            ATTR_DURATION_HOURS: sum(item.hours for item in matching),
            "matching_entries": len(matching),
            "timesheet_ids": [item.id for item in matching],
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_TIME,
        async_handle_log_time,
        schema=BASE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DAY_HOURS,
        async_handle_get_day_hours,
        schema=GET_DAY_HOURS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DAY_HOURS,
        async_handle_set_day_hours,
        schema=BASE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_matching_timesheets(
    entry: KimaiConfigEntry,
    selected_date: date,
    project_id: int,
    activity_id: int,
) -> list[KimaiTimesheet]:
    """Return entries matching one local date, project and activity."""
    day_start = datetime.combine(selected_date, time.min)
    day_end = day_start + timedelta(days=1)
    timesheets = await entry.runtime_data.client.async_get_timesheets(
        day_start, day_end
    )
    return [
        item
        for item in timesheets
        if item.begin.date() == selected_date
        and item.project_id == project_id
        and item.activity_id == activity_id
    ]


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> KimaiConfigEntry:
    """Resolve one loaded Kimai config entry."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id is not None:
        entries = [entry for entry in entries if entry.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=("entry_not_found" if entry_id else "entry_required"),
        )
    return entries[0]


def _resolve_project_activity(
    entry: KimaiConfigEntry,
    data: dict[str, Any],
) -> tuple[int, int]:
    """Resolve explicit or configured default project and activity IDs."""
    project_id = data.get(ATTR_PROJECT_ID) or entry.options.get(CONF_DEFAULT_PROJECT_ID)
    activity_id = data.get(ATTR_ACTIVITY_ID) or entry.options.get(
        CONF_DEFAULT_ACTIVITY_ID
    )
    if project_id is None or activity_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="defaults_required",
        )

    project_id = int(project_id)
    activity_id = int(activity_id)
    snapshot = entry.runtime_data.coordinator.data
    project = next((item for item in snapshot.projects if item.id == project_id), None)
    activity = next(
        (item for item in snapshot.activities if item.id == activity_id), None
    )
    if project is None or activity is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="project_activity_not_found",
        )
    if activity.project_id not in {None, project_id}:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="incompatible_activity",
        )
    return project_id, activity_id


def _time_range(data: dict[str, Any]) -> tuple[datetime, datetime]:
    """Build the naive local datetimes required by Kimai."""
    selected_date: date = data[ATTR_DATE]
    start_time: time = data[ATTR_START_TIME]
    begin = datetime.combine(selected_date, start_time)
    end = begin + timedelta(hours=data[ATTR_DURATION_HOURS])
    return begin, end
