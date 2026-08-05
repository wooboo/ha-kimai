"""Calendar entity for browsing Kimai timesheets."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import KimaiApiError
from .coordinator import KimaiConfigEntry, KimaiDataUpdateCoordinator
from .entity import KimaiEntity
from .models import KimaiTimesheet


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KimaiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kimai calendar."""
    del hass
    async_add_entities([KimaiCalendar(entry.runtime_data.coordinator)])


class KimaiCalendar(KimaiEntity, CalendarEntity):
    """Browse completed and active Kimai entries as calendar events."""

    _attr_translation_key = "timesheets"
    _attr_icon = "mdi:calendar-clock"
    _attr_initial_color = "#4f46e5"

    def __init__(self, coordinator: KimaiDataUpdateCoordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_timesheets"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active or next cached event."""
        now = dt_util.now()
        candidates = sorted(
            (
                item
                for item in self.coordinator.data.timesheets
                if item.end is None or item.end >= now
            ),
            key=lambda item: item.begin,
        )
        return self._event_from_timesheet(candidates[0]) if candidates else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return Kimai entries for the calendar's requested range."""
        del hass
        try:
            timesheets = await self.coordinator.client.async_get_timesheets(
                start_date - timedelta(days=1), end_date
            )
        except KimaiApiError as err:
            raise HomeAssistantError(
                translation_domain="kimai",
                translation_key="calendar_fetch_failed",
            ) from err
        return [
            self._event_from_timesheet(item)
            for item in timesheets
            if item.begin < end_date and (item.end is None or item.end > start_date)
        ]

    def _event_from_timesheet(self, timesheet: KimaiTimesheet) -> CalendarEvent:
        """Convert a Kimai timesheet into a Home Assistant calendar event."""
        end = timesheet.end
        if end is None:
            end = max(
                dt_util.now() + timedelta(minutes=1),
                timesheet.begin + timedelta(minutes=1),
            )
        project = self.coordinator.data.project_name(timesheet.project_id)
        activity = self.coordinator.data.activity_name(timesheet.activity_id)
        description_parts = [f"{timesheet.hours:.2f} h"]
        if timesheet.description:
            description_parts.append(timesheet.description)
        return CalendarEvent(
            start=timesheet.begin,
            end=end,
            summary=f"{project} — {activity}",
            description="\n".join(description_parts),
            uid=str(timesheet.id),
        )
