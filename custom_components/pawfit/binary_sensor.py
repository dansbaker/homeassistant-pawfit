"""Binary sensor platform for Pawfit integration."""

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import callback

from .const import DOMAIN
from .helpers import charging, mode_remaining

_LOGGER = logging.getLogger(__name__)


class PawfitChargingSensor(BinarySensorEntity):
    """Binary sensor for charging status."""

    _attr_should_poll = False

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
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def is_on(self):
        """Return True if the device is charging."""
        if self._coordinator.data is None:
            return None
        data = self._coordinator.data.get(str(self._tracker_id), {})
        return charging(data.get("battery"), data.get("_raw", {}).get("model"))

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.tracker_available(self._tracker_id)

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


class PawfitModeActive(BinarySensorEntity):
    """The same reported timer encoding is used by all three modes."""

    mode = "find"
    mode_icon = "mdi:map-search"
    _attr_should_poll = False

    def __init__(self, tracker, coordinator):
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {self.mode.title()} Mode"
        self._attr_unique_id = f"{tracker['petId']}_{self.mode}_mode_active"
        self._attr_icon = self.mode_icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def is_on(self):
        data = (self._coordinator.data or {}).get(str(self._tracker_id), {})
        return mode_remaining(data.get(self.mode + "_timer")) > 0

    @property
    def available(self):
        return self._coordinator.tracker_available(self._tracker_id)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self):
        self.async_write_ha_state()


class PawfitFindModeActive(PawfitModeActive):
    mode = "find"


class PawfitLightModeActive(PawfitModeActive):
    mode = "light"
    mode_icon = "mdi:flashlight"


class PawfitAlarmModeActive(PawfitModeActive):
    mode = "alarm"
    mode_icon = "mdi:alarm-light"


class PawfitLocatingSensor(BinarySensorEntity):
    """On while a Locate is waiting for fresh positions (fork change)."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._attr_name = "PawFit Locating"
        self._attr_unique_id = f"{entry_id}_locating"

    @property
    def is_on(self):
        return self._coordinator.locate_started is not None

    @property
    def icon(self):
        return "mdi:loading" if self.is_on else "mdi:crosshairs-gps"

    @property
    def extra_state_attributes(self):
        c = self._coordinator
        return {
            "waiting_for": c.locate_waiting_for,
            "cleanup_pending": [
                c.tracker_name(tid) for tid in sorted(c._cleanup_pending)
            ],
            "last_result": c.locate_last_result,
            "last_finished": c.locate_last_finished.isoformat()
            if c.locate_last_finished
            else None,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Pawfit binary sensor entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [PawfitLocatingSensor(coordinator, entry.entry_id)]
    for tracker in coordinator.trackers:
        entities.append(PawfitChargingSensor(tracker, coordinator))
        entities.append(PawfitFindModeActive(tracker, coordinator))
        entities.append(PawfitLightModeActive(tracker, coordinator))
        entities.append(PawfitAlarmModeActive(tracker, coordinator))

    async_add_entities(entities)
