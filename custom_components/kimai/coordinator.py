"""Data update coordinator for Kimai."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    KimaiApiClient,
    KimaiAuthenticationError,
    KimaiConnectionError,
    KimaiResponseError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import KimaiSnapshot

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class KimaiRuntimeData:
    """Runtime objects associated with a Kimai config entry."""

    client: KimaiApiClient
    coordinator: KimaiDataUpdateCoordinator


type KimaiConfigEntry = ConfigEntry[KimaiRuntimeData]


class KimaiDataUpdateCoordinator(DataUpdateCoordinator[KimaiSnapshot]):
    """Coordinate a single periodic Kimai refresh for all entities."""

    config_entry: KimaiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KimaiConfigEntry,
        client: KimaiApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> KimaiSnapshot:
        """Fetch the latest projects, activities and recent entries."""
        now = dt_util.now()
        today_start = dt_util.start_of_local_day(now)
        month_start = today_start.replace(day=1)
        history_start = min(month_start, today_start - timedelta(days=31))
        history_end = today_start + timedelta(days=1)
        try:
            customers = await self.client.async_get_customers()
            projects = await self.client.async_get_projects()
            activities = await self.client.async_get_activities()
            timesheets = await self.client.async_get_timesheets(
                history_start, history_end
            )
        except KimaiAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (KimaiConnectionError, KimaiResponseError, ValueError) as err:
            raise UpdateFailed(str(err)) from err

        return KimaiSnapshot(
            customers=tuple(customers),
            projects=tuple(projects),
            activities=tuple(activities),
            timesheets=tuple(timesheets),
        )
