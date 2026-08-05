"""Base entity for the Kimai integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KimaiDataUpdateCoordinator


class KimaiEntity(CoordinatorEntity[KimaiDataUpdateCoordinator]):
    """Base class shared by Kimai entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KimaiDataUpdateCoordinator) -> None:
        """Initialize a Kimai entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Kimai",
            name=entry.title,
            configuration_url=coordinator.client.base_url,
        )
