"""Binary sensor platform for Pawfit integration."""

import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import callback

from .const import DOMAIN


class PawfitChargingSensor(BinarySensorEntity):
    """Binary sensor for charging status."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Charging"
        self._attr_unique_id = f"{tracker['petId']}_charging"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
        self._attr_icon = "mdi:battery-charging"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def is_on(self):
        """Return True if the device is charging."""
        if self._coordinator.data is None:
            return None
        data = self._coordinator.data.get(self._tracker_id, {})
        battery_raw = data.get("battery")
        if battery_raw is not None:
            return int(battery_raw) < 0
        return None

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Register for coordinator updates
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Pawfit binary sensor entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for tracker in coordinator.trackers:
        entities.append(PawfitChargingSensor(tracker, coordinator))
    
    async_add_entities(entities)
