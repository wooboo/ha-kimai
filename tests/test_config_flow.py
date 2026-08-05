"""Tests for the Kimai config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kimai.const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_DEFAULT_ACTIVITY_ID,
    CONF_DEFAULT_PROJECT_ID,
    DOMAIN,
)


async def test_user_flow_creates_entry(
    hass,
    aioclient_mock,
    kimai_api_payloads: dict,
) -> None:
    """Valid credentials create one account entry."""
    aioclient_mock.get(
        "https://time.example.com/api/users/me",
        json=kimai_api_payloads["profile"],
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.kimai.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "https://time.example.com/",
                CONF_API_TOKEN: "secret-token",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kimai — Piotr"
    assert result["data"][CONF_BASE_URL] == "https://time.example.com"


async def test_user_flow_reports_invalid_auth(hass, aioclient_mock) -> None:
    """An invalid token keeps the user on the form with a useful error."""
    aioclient_mock.get("https://time.example.com/api/users/me", status=403)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_BASE_URL: "https://time.example.com",
            CONF_API_TOKEN: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_selects_defaults(
    hass,
    aioclient_mock,
    kimai_api_payloads: dict,
) -> None:
    """Options offer API-backed project and activity labels."""
    for endpoint in ("customers", "projects", "activities"):
        aioclient_mock.get(
            f"https://time.example.com/api/{endpoint}",
            json=kimai_api_payloads[endpoint],
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BASE_URL: "https://time.example.com",
            CONF_API_TOKEN: "secret-token",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    project_selector = result["data_schema"].schema[
        next(
            key
            for key in result["data_schema"].schema
            if key.schema == CONF_DEFAULT_PROJECT_ID
        )
    ]
    assert project_selector.config["options"] == [
        {"value": "22", "label": "Core / D200"}
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DEFAULT_PROJECT_ID: "22",
            CONF_DEFAULT_ACTIVITY_ID: "33",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEFAULT_PROJECT_ID: 22,
        CONF_DEFAULT_ACTIVITY_ID: 33,
    }
