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
            update_interval=timedelta(seconds=60),  # Default: Poll every 60 seconds
        )
        self.client = client
        self.trackers = trackers
        self.tracker_ids = [t["tracker_id"] for t in trackers]
        self._default_interval = timedelta(seconds=60)
        self._fast_interval = timedelta(seconds=1)
        self.logger.info(f"PawfitDataUpdateCoordinator initialized with trackers: {self.tracker_ids}")

    def _check_any_mode_active(self, data):
        """Check if any tracker has an active mode (find, light, or alarm)."""
        if not data:
            return False
        
        for tracker_id_str, tracker_data in data.items():
            # Check if any timer is active (> 0)
            find_timer = tracker_data.get("find_timer", 0)
            light_timer = tracker_data.get("light_timer", 0)
            alarm_timer = tracker_data.get("alarm_timer", 0)
            
            if any(timer and timer > 0 for timer in [find_timer, light_timer, alarm_timer]):
                # Double check if mode is still within 10 minutes
                import time
                current_time = time.time() * 1000  # Convert to milliseconds
                for timer in [find_timer, light_timer, alarm_timer]:
                    if timer and timer > 0:
                        elapsed = current_time - timer
                        if 0 <= elapsed <= 600000:  # 10 minutes in milliseconds
                            return True
        return False

    def _update_polling_interval(self, data):
        """Update polling interval based on whether any modes are active."""
        any_active = self._check_any_mode_active(data)
        new_interval = self._fast_interval if any_active else self._default_interval
        
        if self.update_interval != new_interval:
            self.update_interval = new_interval
            self.logger.info(f"Updated polling interval to {new_interval.total_seconds()} seconds (modes active: {any_active})")

    async def _async_update_data(self):
        self.logger.info(f"_async_update_data called for trackers: {self.tracker_ids}")
        # Fetch latest location data for all trackers
        location_data = await self.client.async_get_locations(self.tracker_ids)
        
        # Convert location_data keys to strings for consistency with detailed_status keys
        if location_data:
            location_data_str_keys = {str(k): v for k, v in location_data.items()}
            location_data = location_data_str_keys
        
        # Fetch detailed status data including timers
        try:
            detailed_status = await self.client.async_get_detailed_status(self.tracker_ids)
            
            # If detailed_status is a list, convert to dict by tracker ID
            if isinstance(detailed_status, list):
                detailed_dict = {}
                for item in detailed_status:
                    tracker_id = item.get("tracker") or item.get("tracker_id") or item.get("id")
                    if tracker_id:
                        detailed_dict[str(tracker_id)] = item
                    else:
                        self.logger.warning(f"Could not extract tracker_id from detailed status item: {item}")
                detailed_status = detailed_dict
            elif isinstance(detailed_status, dict):
                pass  # Already in correct format
            else:
                self.logger.error(f"Unexpected detailed_status type: {type(detailed_status)}, content: {detailed_status}")
                detailed_status = {}
            
            # Merge the data by tracker ID
            for tracker_id_str, tracker_info in detailed_status.items():
                if tracker_id_str in location_data:
                    # Add timer and status information from detailed status
                    timer_gps = tracker_info.get("timerGps", 0)
                    timer_light = tracker_info.get("timerLight", 0)
                    timer_speaker = tracker_info.get("timerSpeaker", 0)
                    
                    location_data[tracker_id_str].update({
                        "find_timer": timer_gps,
                        "light_timer": timer_light, 
                        "alarm_timer": timer_speaker
                    })
                else:
                    self.logger.warning(f"Tracker {tracker_id_str} from detailed status not found in location_data. Available location data keys: {list(location_data.keys())}")
        except Exception as e:
            self.logger.error(f"Failed to fetch detailed status: {e}", exc_info=True)
            # Continue with just location data if detailed status fails
            
        # Update polling interval based on active modes
        self._update_polling_interval(location_data)
        
        # Fetch activity stats for each tracker
        try:
            for tracker_id in self.tracker_ids:
                activity_stats = await self.client.async_get_activity_stats(str(tracker_id))
                if str(tracker_id) in location_data:
                    location_data[str(tracker_id)].update({
                        "steps_today": activity_stats.get("total_steps", 0),
                        "calories_today": activity_stats.get("total_calories", 0.0),
                        "active_time_today": activity_stats.get("total_active_hours", 0.0)
                    })
                else:
                    self.logger.warning(f"Tracker {tracker_id} not found in location_data for activity stats update")
        except Exception as e:
            self.logger.error(f"Failed to fetch activity stats: {e}", exc_info=True)
            # Continue without activity stats if this fails
            
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
        """Return battery level as a positive integer."""
        if self._attr_battery_level is not None:
            # Ensure we always return a positive value
            return abs(self._attr_battery_level)
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
                logging.debug(f"Tracker {self._tracker_id}: Battery charging - raw: {battery_value}, level: {self._attr_battery_level}")
            else:
                # Positive value indicates not charging
                self._attr_battery_level = battery_value
                self._attr_charging = False
                logging.debug(f"Tracker {self._tracker_id}: Battery not charging - raw: {battery_value}, level: {self._attr_battery_level}")
        else:
            self._attr_battery_level = None
            self._attr_charging = None
        
        # Only log if there's an issue
        if not (self._attr_latitude and self._attr_longitude) and data:
            logging.warning(f"Tracker {self._tracker_id}: No location data available")

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
