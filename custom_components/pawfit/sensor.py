"""Sensor platform for Pawfit integration."""

import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from datetime import datetime, timezone

from .const import DOMAIN


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
        loc = self._coordinator.data.get(self._tracker_id, {})
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
            logging.warning(f"Tracker {self._tracker_id}: No coordinator data available")
            return None
        
        data = self._coordinator.data.get(self._tracker_id, {})
        logging.warning(f"Tracker {self._tracker_id}: Processing timestamp sensor, data keys: {list(data.keys()) if data else 'None'}")
        
        if self._kind == "last_update":
            # Get the timestamp from the raw API data
            raw_data = data.get("_raw", {})
            state_data = raw_data.get("state", {})
            location_data = state_data.get("location", {})
            utc_timestamp = location_data.get("utcDateTime")
            
            logging.warning(f"Tracker {self._tracker_id} timestamp extraction: raw_data exists={raw_data is not None}, state_data exists={state_data is not None}, location_data exists={location_data is not None}, utc_timestamp={utc_timestamp}")
            
            if utc_timestamp:
                try:
                    # Since we're in 2025, treat as seconds (not milliseconds)
                    dt = datetime.fromtimestamp(utc_timestamp, timezone.utc)
                    logging.warning(f"Tracker {self._tracker_id} successfully converted timestamp {utc_timestamp} to datetime: {dt}")
                    return dt
                except (ValueError, TypeError) as e:
                    logging.error(f"Tracker {self._tracker_id} failed to convert timestamp {utc_timestamp}: {e}")
                    return None
            else:
                logging.error(f"Tracker {self._tracker_id}: No utcDateTime found in location data. Location data: {location_data}")
        
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
    
    async_add_entities(entities)
