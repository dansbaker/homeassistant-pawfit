"""Sensor platform for Pawfit integration."""

import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from datetime import datetime, timezone

from .const import DOMAIN
from .helpers import battery_level, mode_remaining
from .device_tracker import fix_time

_LOGGER = logging.getLogger(__name__)


class PawfitSensor(SensorEntity):
    """Base sensor class for Pawfit trackers."""

    _attr_should_poll = False

    def __init__(
        self, tracker, coordinator, kind, name, unit=None, icon=None, device_class=None
    ):
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
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def native_value(self):
        """Return the sensor value."""
        if self._coordinator.data is None:
            _LOGGER.debug(
                f"Sensor {self._attr_name} ({self._kind}): No coordinator data available"
            )
            return None

        loc = self._coordinator.data.get(str(self._tracker_id), {})
        value = loc.get(self._kind)

        # Special handling for battery level
        if self._kind == "battery" and value is not None:
            return battery_level(value, loc.get("_raw", {}).get("model"))

        # Add debug logging specifically for activity sensors
        if self._kind in ["steps_today", "calories_today", "active_time_today"]:
            _LOGGER.debug(
                f"Activity sensor {self._attr_name} ({self._kind}): tracker_data_keys={list(loc.keys())}, value={value}"
            )

        return value

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


class PawfitTimestampSensor(SensorEntity):
    """Sensor for timestamp-based data like Last Time Seen."""

    _attr_should_poll = False

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
            stamp = fix_time(data)
            return (
                datetime.fromtimestamp(stamp, timezone.utc)
                if stamp is not None
                else None
            )
        return None

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


class PawfitTimerSensor(SensorEntity):
    """Sensor for countdown timers (Find Mode and Light Mode)."""

    _attr_should_poll = False

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
        data = (self._coordinator.data or {}).get(str(self._tracker_id), {})
        return int(mode_remaining(data.get(self._timer_type)))

    @property
    def extra_state_attributes(self):
        if self._coordinator.data is None:
            return {}
        remaining = self.native_value
        attributes = {
            "time_remaining_formatted": f"{remaining // 60:02d}:{remaining % 60:02d}"
        }
        if remaining > 0:
            attributes["timer_start_timestamp"] = self._coordinator.data.get(
                str(self._tracker_id), {}
            ).get(self._timer_type)
        return attributes

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.tracker_available(self._tracker_id)

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


class PawfitRequestCountSensor(SensorEntity):
    """Requests this integration has made to Pawfit today (fork change).

    Counts every HTTP request: location and activity fetches, logins and
    Find/Light/Alarm commands.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "requests"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._attr_name = "PawFit API Requests Today"
        self._attr_unique_id = f"{entry_id}_api_requests_today"

    @property
    def native_value(self):
        return self._coordinator.client.requests_today

    @property
    def extra_state_attributes(self):
        client = self._coordinator.client
        return {
            "counting_since": client.counting_since.isoformat(),
            "location_fetches_today": self._coordinator.fetches_today,
            "last_request": client.last_request.isoformat()
            if client.last_request
            else None,
            "requests_since_start": client.request_count,
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
    """Set up Pawfit sensor entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [PawfitRequestCountSensor(coordinator, entry.entry_id)]
    for tracker in coordinator.trackers:
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "battery",
                "Battery Level",
                unit="%",
                device_class=SensorDeviceClass.BATTERY,
            )
        )
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "accuracy",
                "Location Accuracy",
                unit="m",
                icon="mdi:map-marker-radius",
            )
        )
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "signal",
                "Signal Strength",
                unit="dBm",
                icon="mdi:wifi-strength-3",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            )
        )
        entities.append(
            PawfitTimestampSensor(
                tracker,
                coordinator,
                "last_update",
                "Last Time Seen",
                icon="mdi:clock-outline",
            )
        )
        entities.append(
            PawfitTimerSensor(
                tracker,
                coordinator,
                "find_timer",
                "Find Mode Timer",
                icon="mdi:crosshairs-gps",
            )
        )
        entities.append(
            PawfitTimerSensor(
                tracker,
                coordinator,
                "light_timer",
                "Light Mode Timer",
                icon="mdi:lightbulb-on",
            )
        )
        entities.append(
            PawfitTimerSensor(
                tracker,
                coordinator,
                "alarm_timer",
                "Alarm Mode Timer",
                icon="mdi:alarm-light",
            )
        )

        # Add daily activity sensors
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "steps_today",
                "Steps Today",
                unit="steps",
                icon="mdi:walk",
            )
        )
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "calories_today",
                "Calories Today",
                unit="cal",
                icon="mdi:fire",
            )
        )
        entities.append(
            PawfitSensor(
                tracker,
                coordinator,
                "active_time_today",
                "Active Time Today",
                unit="h",
                icon="mdi:clock-time-eight",
            )
        )

    async_add_entities(entities)
