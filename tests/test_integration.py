"""Integration-level tests for entities and actions."""

from datetime import date
from unittest.mock import AsyncMock

from homeassistant.const import ATTR_FRIENDLY_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kimai.const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_DEFAULT_ACTIVITY_ID,
    CONF_DEFAULT_PROJECT_ID,
    DOMAIN,
    SERVICE_LOG_TIME,
    SERVICE_SET_DAY_HOURS,
)
from custom_components.kimai.models import KimaiTimesheet


async def test_setup_creates_entities(hass, mock_overview_api) -> None:
    """One configured account exposes aggregate sensors and a calendar."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kimai — Piotr",
        data={
            CONF_BASE_URL: "https://time.example.com",
            CONF_API_TOKEN: "secret-token",
        },
        options={
            CONF_DEFAULT_PROJECT_ID: 22,
            CONF_DEFAULT_ACTIVITY_ID: 33,
        },
        unique_id="https://time.example.com#7",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 3
    assert {state.state for state in states} == {"0"}
    calendar = hass.states.get("calendar.kimai_piotr_timesheets")
    assert calendar is not None
    assert calendar.attributes[ATTR_FRIENDLY_NAME] == "Kimai — Piotr Timesheets"


async def test_log_time_uses_configured_defaults(
    hass,
    mock_overview_api,
) -> None:
    """The log action creates a completed entry with configured IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kimai — Piotr",
        data={
            CONF_BASE_URL: "https://time.example.com",
            CONF_API_TOKEN: "secret-token",
        },
        options={
            CONF_DEFAULT_PROJECT_ID: 22,
            CONF_DEFAULT_ACTIVITY_ID: 33,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_overview_api.post(
        "https://time.example.com/api/timesheets",
        json={
            "id": 101,
            "begin": "2026-08-05T09:00:00+02:00",
            "end": "2026-08-05T16:30:00+02:00",
            "duration": 27000,
            "project": 22,
            "activity": 33,
            "billable": True,
        },
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_TIME,
        {
            "date": date(2026, 8, 5),
            "duration_hours": 7.5,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"id": 101, "action": "created", "duration_hours": 7.5}
    request = next(call for call in mock_overview_api.mock_calls if call[0] == "POST")
    assert request[2]["project"] == 22
    assert request[2]["activity"] == 33
    assert request[2]["begin"] == "2026-08-05T09:00:00"
    assert request[2]["end"] == "2026-08-05T16:30:00"


async def test_set_day_hours_updates_only_selected_date(
    hass,
    mock_overview_api,
) -> None:
    """The idempotent action ignores an inclusive API result from the next day."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kimai — Piotr",
        data={
            CONF_BASE_URL: "https://time.example.com",
            CONF_API_TOKEN: "secret-token",
        },
        options={
            CONF_DEFAULT_PROJECT_ID: 22,
            CONF_DEFAULT_ACTIVITY_ID: 33,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    selected = KimaiTimesheet.from_api(
        {
            "id": 101,
            "begin": "2026-08-05T09:00:00+02:00",
            "end": "2026-08-05T16:00:00+02:00",
            "duration": 25200,
            "project": 22,
            "activity": 33,
            "description": "Keep me",
        }
    )
    next_day = KimaiTimesheet.from_api(
        {
            "id": 102,
            "begin": "2026-08-06T00:00:00+02:00",
            "end": "2026-08-06T01:00:00+02:00",
            "duration": 3600,
            "project": 22,
            "activity": 33,
        }
    )
    updated = KimaiTimesheet.from_api(
        {
            "id": 101,
            "begin": "2026-08-05T09:00:00+02:00",
            "end": "2026-08-05T17:00:00+02:00",
            "duration": 28800,
            "project": 22,
            "activity": 33,
            "description": "Keep me",
        }
    )
    client = entry.runtime_data.client
    client.async_get_timesheets = AsyncMock(return_value=[selected, next_day])
    client.async_update_timesheet = AsyncMock(return_value=updated)
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DAY_HOURS,
        {
            "date": date(2026, 8, 5),
            "duration_hours": 8,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "id": 101,
        "action": "updated",
        "previous_hours": 7,
        "duration_hours": 8,
    }
    client.async_update_timesheet.assert_awaited_once()
    assert client.async_update_timesheet.await_args.args == (101,)
    assert client.async_update_timesheet.await_args.kwargs["description"] == "Keep me"
