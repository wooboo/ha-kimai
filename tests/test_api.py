"""Tests for the asynchronous Kimai API client."""

from datetime import datetime

import pytest
from homeassistant.helpers import aiohttp_client

from custom_components.kimai.api import (
    KimaiApiClient,
    KimaiAuthenticationError,
    format_kimai_datetime,
)


async def test_bearer_token_and_profile(
    hass,
    aioclient_mock,
    kimai_api_payloads: dict,
) -> None:
    """The client authenticates with the supported Bearer header."""
    aioclient_mock.get(
        "https://time.example.com/api/users/me",
        json=kimai_api_payloads["profile"],
    )
    client = KimaiApiClient(
        aiohttp_client.async_get_clientsession(hass),
        "https://time.example.com/",
        "secret-token",
    )

    profile = await client.async_get_profile()

    assert profile.id == 7
    assert profile.display_name == "Piotr"
    request = aioclient_mock.mock_calls[0]
    assert request[3]["Authorization"] == "Bearer secret-token"


async def test_authentication_error(hass, aioclient_mock) -> None:
    """HTTP authentication failures trigger the dedicated exception."""
    aioclient_mock.get("https://time.example.com/api/users/me", status=401)
    client = KimaiApiClient(
        aiohttp_client.async_get_clientsession(hass),
        "https://time.example.com",
        "wrong",
    )

    with pytest.raises(KimaiAuthenticationError):
        await client.async_get_profile()


def test_datetime_format_is_local_html5() -> None:
    """Writes omit an offset as required by Kimai's API contract."""
    value = datetime.fromisoformat("2026-08-05T09:15:00+02:00")
    assert format_kimai_datetime(value) == "2026-08-05T09:15:00"
