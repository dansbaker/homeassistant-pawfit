import aiohttp
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity import Entity
from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from datetime import datetime, timezone

from .pawfit_api import PawfitApiClient
from .const import DOMAIN
from datetime import timedelta

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

# Fallback for binary sensor imports
try:
    from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
except ImportError:
    class BinarySensorDeviceClass:
        BATTERY_CHARGING = "battery_charging"
    class BinarySensorEntity(Entity):
        pass

# Fallback for sensor imports
try:
    from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
except ImportError:
    class SensorDeviceClass:
        TIMESTAMP = "timestamp"
    class SensorEntity(Entity):
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
        data = await self.client.async_get_locations(self.tracker_ids)
        return data

class PawfitSensor(Entity):
    def __init__(self, tracker, coordinator, kind, name, unit=None, icon=None):
        self._tracker = tracker
        self._coordinator = coordinator
        self._kind = kind  # e.g. 'battery', 'accuracy', 'signal', etc.
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {name}"
        self._attr_unique_id = f"{tracker['petId']}_{kind}"
        self._tracker_id = tracker["tracker_id"]
        self._unit = unit
        self._icon = icon

    @property
    def name(self):
        return self._attr_name

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def state(self):
        if self._coordinator.data is None:
            return None
        loc = self._coordinator.data.get(self._tracker_id, {})
        return loc.get(self._kind)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{self._tracker['name']}'s PawFit Tracker",
            "model": self._tracker.get("model", "Unknown"),
        }

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

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

    @property
    def state(self):
        if self._attr_latitude is not None and self._attr_longitude is not None:
            return f"{self._attr_latitude}, {self._attr_longitude}"
        return None

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
            "model": tracker.get("model", "Unknown"),
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
    """Set up Pawfit device tracker and sensor entities from a config entry."""
    session = aiohttp.ClientSession()
    client = PawfitApiClient(
        entry.data["username"],
        entry.data["password"],
        session
    )
    trackers = await client.async_get_trackers()
    coordinator = PawfitDataUpdateCoordinator(hass, client, trackers)
    
    # Start the coordinator to begin polling
    await coordinator.async_config_entry_first_refresh()
    
    entities = []
    for tracker in trackers:
        entities.append(PawfitDeviceTracker(tracker, coordinator))
        entities.append(PawfitSensor(tracker, coordinator, "battery", "Battery Level", unit="%", icon="mdi:battery-medium"))
        entities.append(PawfitChargingSensor(tracker, coordinator))
        entities.append(PawfitSensor(tracker, coordinator, "accuracy", "Location Accuracy", unit="m", icon="mdi:map-marker-radius"))
        entities.append(PawfitSensor(tracker, coordinator, "signal", "Signal Strength", unit="db", icon="mdi:wifi-strength-3"))
        entities.append(PawfitTimestampSensor(tracker, coordinator, "last_update", "Last Time Seen", icon="mdi:clock-outline"))
    async_add_entities(entities)
