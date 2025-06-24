"""Binary sensor platform for Pawfit integration."""

import logging
from datetime import datetime, timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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


class PawfitFindModeActive(BinarySensorEntity):
    """Binary sensor for Find Mode active status."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Find Mode"
        self._attr_unique_id = f"{tracker['petId']}_find_mode_active"
        self._attr_icon = "mdi:map-search"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def is_on(self):
        """Return True if Find Mode is active."""
        if self._coordinator.data is None:
            return False
        
        data = self._coordinator.data.get(self._tracker_id, {})
        find_timer = data.get("find_timer")
        
        _LOGGER.debug(f"Find mode check for tracker {self._tracker_id}: find_timer={find_timer}")
        
        if find_timer is None or find_timer == 0:
            _LOGGER.debug(f"Find mode inactive for tracker {self._tracker_id}: timer is None or 0")
            return False
        
        # Check if within 10 minutes (600 seconds) of timer start
        try:
            import time
            # Timer values from API are in milliseconds, convert to seconds
            timer_start_seconds = find_timer / 1000.0
            current_time_seconds = time.time()
            elapsed_seconds = current_time_seconds - timer_start_seconds
            
            _LOGGER.debug(f"Find mode timer check for tracker {self._tracker_id}: timer_start={timer_start_seconds}, current={current_time_seconds}, elapsed={elapsed_seconds}")
            
            is_active = elapsed_seconds < 600 and elapsed_seconds >= 0  # 10 minutes and not in future
            _LOGGER.debug(f"Find mode active for tracker {self._tracker_id}: {is_active}")
            return bool(is_active)  # Ensure it's explicitly a boolean
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid find timer value for tracker %s: %s", self._tracker_id, find_timer)
            return False

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return "on" if self.is_on else "off"

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


class PawfitLightModeActive(BinarySensorEntity):
    """Binary sensor for Light Mode active status."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Light Mode"
        self._attr_unique_id = f"{tracker['petId']}_light_mode_active"
        self._attr_icon = "mdi:flashlight"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def is_on(self):
        """Return True if Light Mode is active."""
        if self._coordinator.data is None:
            return False
        
        data = self._coordinator.data.get(self._tracker_id, {})
        light_timer_start = data.get("light_timer")
        
        _LOGGER.debug(f"Light mode check for tracker {self._tracker_id}: light_timer={light_timer_start}")
        
        if light_timer_start is None or light_timer_start == 0:
            _LOGGER.debug(f"Light mode inactive for tracker {self._tracker_id}: timer is None or 0")
            return False
        
        # Check if within 10 minutes (600 seconds) of timer start
        try:
            import time
            # Timer values from API are in milliseconds, convert to seconds
            timer_start_seconds = light_timer_start / 1000.0
            current_time_seconds = time.time()
            elapsed_seconds = current_time_seconds - timer_start_seconds
            
            _LOGGER.debug(f"Light mode timer check for tracker {self._tracker_id}: timer_start={timer_start_seconds}, current={current_time_seconds}, elapsed={elapsed_seconds}")
            
            is_active = elapsed_seconds < 600 and elapsed_seconds >= 0  # 10 minutes and not in future
            _LOGGER.debug(f"Light mode active for tracker {self._tracker_id}: {is_active}")
            return bool(is_active)  # Ensure it's explicitly a boolean
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid light timer value for tracker %s: %s", self._tracker_id, light_timer_start)
            return False

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return "on" if self.is_on else "off"

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


class PawfitAlarmModeActive(BinarySensorEntity):
    """Binary sensor for Alarm Mode active status."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Alarm Mode"
        self._attr_unique_id = f"{tracker['petId']}_alarm_mode_active"
        self._attr_icon = "mdi:alarm-light"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def is_on(self):
        """Return True if Alarm Mode is active."""
        if self._coordinator.data is None:
            return False
        
        data = self._coordinator.data.get(self._tracker_id, {})
        alarm_timer = data.get("alarm_timer")
        
        _LOGGER.debug(f"Alarm mode check for tracker {self._tracker_id}: alarm_timer={alarm_timer}")
        
        if alarm_timer is None or alarm_timer == 0:
            _LOGGER.debug(f"Alarm mode inactive for tracker {self._tracker_id}: timer is None or 0")
            return False
        
        # Check if within 10 minutes (600 seconds) of timer start
        try:
            import time
            # Timer values from API are in milliseconds, convert to seconds
            timer_start_seconds = alarm_timer / 1000.0
            current_time_seconds = time.time()
            elapsed_seconds = current_time_seconds - timer_start_seconds
            
            _LOGGER.debug(f"Alarm mode timer check for tracker {self._tracker_id}: timer_start={timer_start_seconds}, current={current_time_seconds}, elapsed={elapsed_seconds}")
            
            is_active = elapsed_seconds < 600 and elapsed_seconds >= 0  # 10 minutes and not in future
            _LOGGER.debug(f"Alarm mode active for tracker {self._tracker_id}: {is_active}")
            return bool(is_active)  # Ensure it's explicitly a boolean
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid alarm timer value for tracker %s: %s", self._tracker_id, alarm_timer)
            return False

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return "on" if self.is_on else "off"

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
        entities.append(PawfitFindModeActive(tracker, coordinator))
        entities.append(PawfitLightModeActive(tracker, coordinator))
        entities.append(PawfitAlarmModeActive(tracker, coordinator))
    
    async_add_entities(entities)
