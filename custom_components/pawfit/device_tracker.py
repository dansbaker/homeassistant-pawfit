import aiohttp
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity import Entity
from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.core import callback
from datetime import datetime, timezone, timedelta

from .pawfit_api import PawfitApiClient
from .const import DOMAIN

# Define SOURCE_TYPE_GPS constant for device tracker
SOURCE_TYPE_GPS = "gps"

# Fallback: define DeviceTrackerEntity as base Entity if import fails
try:
    from homeassistant.components.device_tracker import TrackerEntity, SourceType
except ImportError:
    class SourceType:
        GPS = "gps"
    class TrackerEntity(Entity):
        pass

class PawfitDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, trackers):
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=60),  # Poll every 60 seconds
        )
        self.client = client
        self.trackers = trackers
        self.tracker_ids = [t["tracker_id"] for t in trackers]

    async def _async_update_data(self):
        # Fetch latest location data for all trackers
        location_data = await self.client.async_get_locations(self.tracker_ids)
        
        # Fetch detailed status data including timers
        try:
            detailed_status = await self.client.async_get_detailed_status()
            
            # Merge the data by tracker ID
            for tracker_info in detailed_status:
                tracker_id = tracker_info.get("tracker")
                if tracker_id and tracker_id in location_data:
                    # Add timer and status information
                    location_data[tracker_id].update({
                        "timer_gps": tracker_info.get("timerGps", 0),
                        "timer_light": tracker_info.get("timerLight", 0)
                    })
        except Exception as e:
            logging.warning(f"Failed to fetch detailed status: {e}")
            # Continue with just location data if detailed status fails
        
        return location_data

class PawfitDeviceTracker(TrackerEntity):
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker"
        self._attr_unique_id = str(tracker["petId"])
        self._attr_icon = "mdi:paw"
        self._attr_source_type = SourceType.GPS
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit",
            "translation_key": "pawfit_tracker",
        }
        self._attr_latitude = None
        self._attr_longitude = None
        self._attr_location_accuracy = None
        self._attr_battery_level = None
        self._attr_charging = None

    @property
    def battery_level(self):
        return self._attr_battery_level

    @property
    def charging(self):
        return self._attr_charging

    @property
    def source_type(self):
        return self._attr_source_type

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success and self._attr_latitude is not None and self._attr_longitude is not None

    def _update_attrs(self):
        data = self._coordinator.data.get(self._tracker_id, {}) if self._coordinator.data else {}
        self._attr_latitude = float(data.get("latitude")) if data.get("latitude") else None
        self._attr_longitude = float(data.get("longitude")) if data.get("longitude") else None
        self._attr_location_accuracy = float(data.get("accuracy")) if data.get("accuracy") else None
        
        # Handle battery level and charging status
        battery_raw = data.get("battery")
        if battery_raw is not None:
            battery_value = int(battery_raw)
            if battery_value < 0:
                # Negative value indicates charging
                self._attr_battery_level = abs(battery_value)
                self._attr_charging = True
            else:
                # Positive value indicates not charging
                self._attr_battery_level = battery_value
                self._attr_charging = False
        else:
            self._attr_battery_level = None
            self._attr_charging = None
        
        # Only log if we have location data or if something is wrong
        if self._attr_latitude and self._attr_longitude:
            logging.debug(f"Tracker {self._tracker_id}: Updated location to {self._attr_latitude}, {self._attr_longitude}")
        elif data:
            logging.warning(f"Tracker {self._tracker_id}: No location data in: {data}")
        else:
            logging.warning(f"Tracker {self._tracker_id}: No data available from coordinator")

    async def async_update(self):
        await self._coordinator.async_request_refresh()
        self._update_attrs()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_attrs()
        # Register for coordinator updates
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Pawfit device tracker entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for tracker in coordinator.trackers:
        entities.append(PawfitDeviceTracker(tracker, coordinator))
    
    async_add_entities(entities)
