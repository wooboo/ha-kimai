"""Shared fixtures for Kimai tests."""

from collections.abc import Generator

import pytest
from homeassistant.core import HomeAssistant

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def kimai_api_payloads() -> dict:
    """Return representative modern Kimai API responses."""
    return {
        "profile": {"id": 7, "username": "piotr", "displayName": "Piotr"},
        "customers": [{"id": 11, "name": "Core"}],
        "projects": [{"id": 22, "name": "D200", "customer": 11}],
        "activities": [{"id": 33, "name": "Development", "project": 22}],
    }


@pytest.fixture
def mock_overview_api(
    hass: HomeAssistant,
    aioclient_mock,
    kimai_api_payloads: dict,
):
    """Mock endpoints requested during coordinator setup."""
    del hass
    aioclient_mock.get(
        "https://time.example.com/api/customers",
        json=kimai_api_payloads["customers"],
    )
    aioclient_mock.get(
        "https://time.example.com/api/projects",
        json=kimai_api_payloads["projects"],
    )
    aioclient_mock.get(
        "https://time.example.com/api/activities",
        json=kimai_api_payloads["activities"],
    )
    aioclient_mock.get("https://time.example.com/api/timesheets", json=[])
    return aioclient_mock
