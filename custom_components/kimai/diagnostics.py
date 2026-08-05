"""Diagnostics support for Kimai."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN
from .coordinator import KimaiConfigEntry

TO_REDACT = {CONF_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: KimaiConfigEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics for a Kimai config entry."""
    del hass
    snapshot = entry.runtime_data.coordinator.data
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "counts": {
            "activities": len(snapshot.activities),
            "customers": len(snapshot.customers),
            "projects": len(snapshot.projects),
            "timesheets_in_window": len(snapshot.timesheets),
        },
    }
