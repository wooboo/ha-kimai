"""Sensor entities provided by Kimai."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import KimaiConfigEntry, KimaiDataUpdateCoordinator
from .entity import KimaiEntity
from .models import KimaiSnapshot


@dataclass(frozen=True, kw_only=True)
class KimaiSensorEntityDescription(SensorEntityDescription):
    """Describe a Kimai duration sensor."""

    value_fn: Callable[[KimaiSnapshot, date], float]


def _today_hours(snapshot: KimaiSnapshot, today: date) -> float:
    return snapshot.hours_for_date(today)


def _week_hours(snapshot: KimaiSnapshot, today: date) -> float:
    week_start = today - timedelta(days=today.weekday())
    return sum(
        item.hours
        for item in snapshot.timesheets
        if week_start <= item.begin.date() <= today
    )


def _month_hours(snapshot: KimaiSnapshot, today: date) -> float:
    return sum(
        item.hours
        for item in snapshot.timesheets
        if item.begin.year == today.year and item.begin.month == today.month
    )


SENSOR_DESCRIPTIONS = (
    KimaiSensorEntityDescription(
        key="today_hours",
        translation_key="today_hours",
        icon="mdi:clock-check-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=_today_hours,
    ),
    KimaiSensorEntityDescription(
        key="week_hours",
        translation_key="week_hours",
        icon="mdi:calendar-week",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=_week_hours,
    ),
    KimaiSensorEntityDescription(
        key="month_hours",
        translation_key="month_hours",
        icon="mdi:calendar-month",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=_month_hours,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KimaiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kimai sensors from a config entry."""
    del hass
    async_add_entities(
        KimaiDurationSensor(entry.runtime_data.coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class KimaiDurationSensor(KimaiEntity, SensorEntity):
    """A duration aggregated from recent Kimai timesheets."""

    entity_description: KimaiSensorEntityDescription

    def __init__(
        self,
        coordinator: KimaiDataUpdateCoordinator,
        description: KimaiSensorEntityDescription,
    ) -> None:
        """Initialize the duration sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the current aggregate in decimal hours."""
        return round(
            self.entity_description.value_fn(
                self.coordinator.data, dt_util.now().date()
            ),
            4,
        )

    @property
    def extra_state_attributes(self) -> dict[str, dict[str, float]] | None:
        """Expose daily totals for the last seven days on today's sensor."""
        if self.entity_description.key != "today_hours":
            return None
        today = dt_util.now().date()
        return {
            "daily_hours": {
                (today - timedelta(days=offset)).isoformat(): round(
                    self.coordinator.data.hours_for_date(
                        today - timedelta(days=offset)
                    ),
                    4,
                )
                for offset in range(6, -1, -1)
            }
        }
