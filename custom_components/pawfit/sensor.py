"""Sensor platform for Pawfit integration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PawfitSensor(SensorEntity):
    """Base sensor class for Pawfit trackers."""
    
    def __init__(
        self, 
        tracker: Dict[str, Any], 
        coordinator: Any, 
        kind: str, 
        name: str, 
        unit: Optional[str] = None, 
        icon: Optional[str] = None, 
        device_class: Optional[SensorDeviceClass] = None
    ) -> None:
        """Initialize the sensor.
        
        Args:
            tracker: Tracker information dictionary
            coordinator: Data update coordinator
            kind: Type of sensor data
            name: Human readable name
            unit: Unit of measurement
            icon: Icon to use
            device_class: Device class for the sensor
        """
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
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown")
        }

    @property
    def native_value(self) -> Optional[float]:
        """Return the sensor value."""
        if self._coordinator.data is None:
            _LOGGER.debug(f"Sensor {self._attr_name} ({self._kind}): No coordinator data available")
            return None
        
        loc = self._coordinator.data.get(str(self._tracker_id), {})
        value = loc.get(self._kind)
        
        # Add debug logging specifically for activity sensors
        if self._kind in ["steps_today", "calories_today", "active_time_today"]:
            _LOGGER.debug(f"Activity sensor {self._attr_name} ({self._kind}): tracker_data_keys={list(loc.keys())}, value={value}")
            if value == 0 or value is None:
                _LOGGER.warning(f"Activity sensor {self._attr_name} ({self._kind}) is zero or None. Full tracker data: {loc}")
        
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
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
    
    def __init__(
        self, 
        tracker: Dict[str, Any], 
        coordinator: Any, 
        kind: str, 
        name: str, 
        icon: Optional[str] = None
    ) -> None:
        """Initialize the timestamp sensor.
        
        Args:
            tracker: Tracker information dictionary
            coordinator: Data update coordinator
            kind: Type of timestamp data
            name: Human readable name
            icon: Icon to use
        """
        self._tracker = tracker
        self._coordinator = coordinator
        self._kind = kind
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{kind}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = icon or "mdi:clock-outline"
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def native_value(self) -> Optional[datetime]:
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
                    _LOGGER.error(f"Tracker {self._tracker_id} failed to convert timestamp {utc_timestamp}: {e}")
                    return None
            else:
                _LOGGER.error(f"Tracker {self._tracker_id}: No utcDateTime found in location data")
        
        _LOGGER.error(f"Tracker {self._tracker_id}: Returning None for timestamp sensor")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
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
    
    def __init__(
        self, 
        tracker: Dict[str, Any], 
        coordinator: Any, 
        timer_type: str, 
        name: str, 
        icon: Optional[str] = None
    ) -> None:
        """Initialize the timer sensor.
        
        Args:
            tracker: Tracker information dictionary
            coordinator: Data update coordinator
            timer_type: Type of timer ('timer' or 'light_timer')
            name: Human readable name
            icon: Icon to use
        """
        self._tracker = tracker
        self._coordinator = coordinator
        self._timer_type = timer_type  # 'timer' or 'light_timer'
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{timer_type}_countdown"
        self._attr_native_unit_of_measurement = "s"  # seconds
        self._attr_icon = icon or "mdi:timer"
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit",
            "translation_key": "pawfit_tracker",
        }

    @property
    def native_value(self) -> int:
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
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if self._coordinator.data is None:
            return {}
        
        data = self._coordinator.data.get(str(self._tracker_id), {})
        timer_start = data.get(self._timer_type, 0)
        
        attributes: Dict[str, Any] = {}
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
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant, 
    entry: Any, 
    async_add_entities: Any
) -> None:
    """Set up Pawfit sensor entities from a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        async_add_entities: Function to add entities
    """
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: List[SensorEntity] = []
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
