"""Sensor platform for Pawfit integration."""

import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from datetime import datetime, timezone

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PawfitSensor(SensorEntity):
    """Base sensor class for Pawfit trackers."""
    
    def __init__(self, tracker, coordinator, kind, name, unit=None, icon=None, device_class=None):
        self._tracker = tracker
        self._coordinator = coordinator
        self._kind = kind  # e.g. 'battery', 'accuracy', 'signal', etc.
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{kind}"
        self._tracker_id = tracker["tracker_id"]
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if device_class:
            self._attr_device_class = device_class
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def native_value(self):
        """Return the sensor value."""
        if self._coordinator.data is None:
            return None
        loc = self._coordinator.data.get(str(self._tracker_id), {})
        return loc.get(self._kind)

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


class PawfitTimestampSensor(SensorEntity):
    """Sensor for timestamp-based data like Last Time Seen."""
    
    def __init__(self, tracker, coordinator, kind, name, icon=None):
        self._tracker = tracker
        self._coordinator = coordinator
        self._kind = kind
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{kind}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = icon or "mdi:clock-outline"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def native_value(self):
        """Return the timestamp as a datetime object."""
        if self._coordinator.data is None:
            return None
        
        data = self._coordinator.data.get(str(self._tracker_id), {})
        
        if self._kind == "last_update":
            # Get the timestamp from the raw API data
            raw_data = data.get("_raw", {})
            state_data = raw_data.get("state", {})
            location_data = state_data.get("location", {})
            utc_timestamp = location_data.get("utcDateTime")
            
            if utc_timestamp:
                try:
                    dt = datetime.fromtimestamp(utc_timestamp, timezone.utc)
                    return dt
                except (ValueError, TypeError) as e:
                    logging.error(f"Tracker {self._tracker_id} failed to convert timestamp {utc_timestamp}: {e}")
                    return None
            else:
                logging.error(f"Tracker {self._tracker_id}: No utcDateTime found in location data")
        
        logging.error(f"Tracker {self._tracker_id}: Returning None for timestamp sensor")
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


class PawfitTimerSensor(SensorEntity):
    """Sensor for countdown timers (Find Mode and Light Mode)."""
    
    def __init__(self, tracker, coordinator, timer_type, name, icon=None):
        self._tracker = tracker
        self._coordinator = coordinator
        self._timer_type = timer_type  # 'timer' or 'light_timer'
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{timer_type}_countdown"
        self._attr_native_unit_of_measurement = "s"  # seconds
        self._attr_icon = icon or "mdi:timer"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit",
            "translation_key": "pawfit_tracker",
        }

    @property
    def native_value(self):
        """Return the remaining time in seconds."""
        if self._coordinator.data is None:
            return 0
        
        data = self._coordinator.data.get(str(self._tracker_id), {})
        timer_start = data.get(self._timer_type, 0)
        
        if timer_start and timer_start > 0:
            try:
                import time
                # Timer values from API are in milliseconds, convert to seconds
                timer_start_seconds = timer_start / 1000.0
                current_time_seconds = time.time()
                elapsed_seconds = current_time_seconds - timer_start_seconds
                
                # 10 minutes = 600 seconds
                remaining_seconds = 600 - elapsed_seconds
                
                if remaining_seconds > 0:
                    return int(remaining_seconds)
                else:
                    return 0
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid timer value for {self._timer_type} on tracker {self._tracker_id}: {timer_start}")
                return 0
        
        return 0

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self._coordinator.data is None:
            return {}
        
        data = self._coordinator.data.get(str(self._tracker_id), {})
        timer_start = data.get(self._timer_type, 0)
        
        attributes = {}
        if timer_start and timer_start > 0:
            # Add formatted time remaining
            remaining_seconds = self.native_value
            if remaining_seconds > 0:
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                attributes["time_remaining_formatted"] = f"{minutes:02d}:{seconds:02d}"
                attributes["timer_start_timestamp"] = timer_start
            else:
                attributes["time_remaining_formatted"] = "00:00"
        else:
            attributes["time_remaining_formatted"] = "00:00"
        
        return attributes

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Pawfit sensor entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for tracker in coordinator.trackers:
        entities.append(PawfitSensor(tracker, coordinator, "battery", "Battery Level", unit="%", icon="mdi:battery-medium", device_class=SensorDeviceClass.BATTERY))
        entities.append(PawfitSensor(tracker, coordinator, "accuracy", "Location Accuracy", unit="m", icon="mdi:map-marker-radius"))
        entities.append(PawfitSensor(tracker, coordinator, "signal", "Signal Strength", unit="dBm", icon="mdi:wifi-strength-3", device_class=SensorDeviceClass.SIGNAL_STRENGTH))
        entities.append(PawfitTimestampSensor(tracker, coordinator, "last_update", "Last Time Seen", icon="mdi:clock-outline"))
        entities.append(PawfitTimerSensor(tracker, coordinator, "find_timer", "Find Mode Timer", icon="mdi:crosshairs-gps"))
        entities.append(PawfitTimerSensor(tracker, coordinator, "light_timer", "Light Mode Timer", icon="mdi:lightbulb-on"))
        entities.append(PawfitTimerSensor(tracker, coordinator, "alarm_timer", "Alarm Mode Timer", icon="mdi:alarm-light"))
        
        # Add daily activity sensors
        entities.append(PawfitSensor(tracker, coordinator, "steps_today", "Steps Today", unit="steps", icon="mdi:walk"))
        entities.append(PawfitSensor(tracker, coordinator, "calories_today", "Calories Today", unit="cal", icon="mdi:fire"))
        entities.append(PawfitSensor(tracker, coordinator, "active_time_today", "Active Time Today", unit="h", icon="mdi:clock-time-eight"))
    
    async_add_entities(entities)
