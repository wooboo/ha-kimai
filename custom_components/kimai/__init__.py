"""Kimai time tracking integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv

from .api import KimaiApiClient
from .const import CONF_API_TOKEN, CONF_BASE_URL, DOMAIN, PLATFORMS
from .coordinator import KimaiConfigEntry, KimaiDataUpdateCoordinator, KimaiRuntimeData
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up globally registered Kimai actions."""
    del config
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KimaiConfigEntry) -> bool:
    """Set up Kimai from a config entry."""
    client = KimaiApiClient(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_API_TOKEN],
    )
    coordinator = KimaiDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = KimaiRuntimeData(client=client, coordinator=coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KimaiConfigEntry) -> bool:
    """Unload a Kimai config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload an entry after its options or credentials change."""
    await hass.config_entries.async_reload(entry.entry_id)
