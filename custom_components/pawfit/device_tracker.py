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
        self.logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger=self.logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),  # Poll every 60 seconds
        )
        self.client = client
        self.trackers = trackers
        self.tracker_ids = [t["tracker_id"] for t in trackers]
        self.logger.info(f"PawfitDataUpdateCoordinator initialized with trackers: {self.tracker_ids}")

    async def _async_update_data(self):
        self.logger.info(f"_async_update_data called for trackers: {self.tracker_ids}")
        # Fetch latest location data for all trackers
        self.logger.debug(f"Fetching location data for trackers: {self.tracker_ids}")
        location_data = await self.client.async_get_locations(self.tracker_ids)
        self.logger.debug(f"Location data fetched successfully, keys: {list(location_data.keys()) if location_data else 'No data'}")
        
        # Convert location_data keys to strings for consistency with detailed_status keys
        if location_data:
            location_data_str_keys = {str(k): v for k, v in location_data.items()}
            location_data = location_data_str_keys
            self.logger.debug(f"Converted location_data keys to strings: {list(location_data.keys())}")
        
        # Fetch detailed status data including timers
        try:
            self.logger.debug(f"Fetching detailed status for trackers: {self.tracker_ids}")
            detailed_status = await self.client.async_get_detailed_status(self.tracker_ids)
            self.logger.debug(f"Detailed status response type: {type(detailed_status)}, content: {detailed_status}")
            
            # If detailed_status is a list, convert to dict by tracker ID
            if isinstance(detailed_status, list):
                self.logger.debug(f"Converting detailed_status list to dict, list length: {len(detailed_status)}")
                detailed_dict = {}
                for item in detailed_status:
                    tracker_id = item.get("tracker") or item.get("tracker_id") or item.get("id")
                    self.logger.debug(f"Processing detailed status item: tracker_id={tracker_id}, item_keys={list(item.keys()) if isinstance(item, dict) else 'Not dict'}")
                    if tracker_id:
                        detailed_dict[str(tracker_id)] = item
                        self.logger.debug(f"Added tracker {tracker_id} to detailed_dict with timers: timerGps={item.get('timerGps', 'missing')}, timerLight={item.get('timerLight', 'missing')}, timerSpeaker={item.get('timerSpeaker', 'missing')}")
                    else:
                        self.logger.warning(f"Could not extract tracker_id from detailed status item: {item}")
                detailed_status = detailed_dict
                self.logger.debug(f"Converted detailed_status list to dict with keys: {list(detailed_status.keys())}")
            elif isinstance(detailed_status, dict):
                self.logger.debug(f"Detailed status is already a dict with keys: {list(detailed_status.keys())}")
            else:
                self.logger.error(f"Unexpected detailed_status type: {type(detailed_status)}, content: {detailed_status}")
                detailed_status = {}
            
            self.logger.debug(f"Location data keys: {list(location_data.keys()) if location_data else 'No location data'}")
            self.logger.debug(f"Detailed status keys: {list(detailed_status.keys()) if isinstance(detailed_status, dict) else f'Not dict: {type(detailed_status)}'}")
            
            # Merge the data by tracker ID
            for tracker_id_str, tracker_info in detailed_status.items():
                self.logger.debug(f"Checking tracker {tracker_id_str} - exists in location_data: {tracker_id_str in location_data}")
                if tracker_id_str in location_data:
                    # Add timer and status information from detailed status
                    # Map the timer fields from API response to consistent names
                    timer_gps = tracker_info.get("timerGps", 0)
                    timer_light = tracker_info.get("timerLight", 0)
                    timer_speaker = tracker_info.get("timerSpeaker", 0)
                    
                    self.logger.debug(f"Extracted timer values for tracker {tracker_id_str}: timerGps={timer_gps}, timerLight={timer_light}, timerSpeaker={timer_speaker}")
                    
                    # Validate location_data structure before updating
                    self.logger.debug(f"Location data for tracker {tracker_id_str} before timer merge: {location_data[tracker_id_str]}")
                    
                    location_data[tracker_id_str].update({
                        "find_timer": timer_gps,
                        "light_timer": timer_light, 
                        "alarm_timer": timer_speaker
                    })
                    self.logger.debug(f"Updated tracker {tracker_id_str} with timers: find_timer={timer_gps}, light_timer={timer_light}, alarm_timer={timer_speaker}")
                    self.logger.debug(f"Final location_data for tracker {tracker_id_str}: {location_data[tracker_id_str]}")
                    
                    # Verify the merge worked
                    verify_find = location_data[tracker_id_str].get("find_timer")
                    verify_light = location_data[tracker_id_str].get("light_timer") 
                    verify_alarm = location_data[tracker_id_str].get("alarm_timer")
                    self.logger.debug(f"POST-MERGE VERIFICATION - Tracker {tracker_id_str}: find_timer={verify_find}, light_timer={verify_light}, alarm_timer={verify_alarm}")
                else:
                    self.logger.warning(f"Tracker {tracker_id_str} from detailed status not found in location_data. Available location data keys: {list(location_data.keys())}")
        except Exception as e:
            self.logger.error(f"Failed to fetch detailed status: {e}", exc_info=True)
            # Continue with just location data if detailed status fails
            
        self.logger.debug(f"Final coordinator data being returned: {location_data}")
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
        data = self._coordinator.data.get(str(self._tracker_id), {}) if self._coordinator.data else {}
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
