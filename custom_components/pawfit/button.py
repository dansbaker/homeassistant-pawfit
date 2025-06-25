"""Button platform for Pawfit integration."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PawfitFindModeButton(ButtonEntity):
    """Button to activate/deactivate Find Mode."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Find Mode"
        self._attr_unique_id = f"{tracker['petId']}_find_mode_button"
        self._attr_icon = "mdi:crosshairs-gps"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit",
        }

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # Check if find mode is currently active
            data = self._coordinator.data.get(str(self._tracker_id), {}) if self._coordinator.data else {}
            find_timer = data.get("find_timer", 0)
            
            if find_timer and find_timer > 0:
                # Check if within 10 minutes (active)
                import time
                try:
                    # Timer values from API are in milliseconds, convert to seconds
                    timer_start_seconds = find_timer / 1000.0
                    current_time_seconds = time.time()
                    elapsed_seconds = current_time_seconds - timer_start_seconds
                    is_active = elapsed_seconds < 600  # 10 minutes
                    
                    if is_active:
                        # Find mode is active, so stop it
                        success = await self._coordinator.client.async_stop_find_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully stopped find mode for tracker {self._tracker_id}")
                            # Trigger immediate coordinator update
                            await self._coordinator.async_request_refresh()
                        else:
                            raise HomeAssistantError(f"Failed to stop find mode for tracker {self._tracker_id}")
                    else:
                        # Timer expired, start new find mode
                        success = await self._coordinator.client.async_start_find_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully started find mode for tracker {self._tracker_id}")
                            # Immediately switch to fast polling and trigger update
                            _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_set_fast_polling()
                            _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_request_refresh()
                            _LOGGER.debug("Requested immediate refresh after starting find mode")
                        else:
                            raise HomeAssistantError(f"Failed to start find mode for tracker {self._tracker_id}")
                except (ValueError, TypeError):
                    # Invalid timer, start new find mode
                    success = await self._coordinator.client.async_start_find_mode(str(self._tracker_id))
                    if success:
                        _LOGGER.info(f"Successfully started find mode for tracker {self._tracker_id}")
                        # Immediately switch to fast polling and trigger update
                        _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_set_fast_polling()
                        _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_request_refresh()
                        _LOGGER.debug("Requested immediate refresh after starting find mode")
                    else:
                        raise HomeAssistantError(f"Failed to start find mode for tracker {self._tracker_id}")
            else:                        # Find mode is not active, so start it
                        success = await self._coordinator.client.async_start_find_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully started find mode for tracker {self._tracker_id}")
                            # Immediately switch to fast polling and trigger update
                            _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_set_fast_polling()
                            _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_request_refresh()
                            _LOGGER.debug("Requested immediate refresh after starting find mode")
                        else:
                            raise HomeAssistantError(f"Failed to start find mode for tracker {self._tracker_id}")
        except Exception as e:
            _LOGGER.error(f"Error controlling find mode for tracker {self._tracker_id}: {e}")
            raise HomeAssistantError(f"Error controlling find mode: {e}")

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


class PawfitLightModeButton(ButtonEntity):
    """Button to activate/deactivate Light Mode."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Light Mode"
        self._attr_unique_id = f"{tracker['petId']}_light_mode_button"
        self._attr_icon = "mdi:flashlight"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit"
        }

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # Check if light mode is currently active
            data = self._coordinator.data.get(str(self._tracker_id), {}) if self._coordinator.data else {}
            light_timer = data.get("light_timer", 0)
            
            if light_timer and light_timer > 0:
                # Check if within 10 minutes (active)
                import time
                try:
                    # Timer values from API are in milliseconds, convert to seconds
                    timer_start_seconds = light_timer / 1000.0
                    current_time_seconds = time.time()
                    elapsed_seconds = current_time_seconds - timer_start_seconds
                    is_active = elapsed_seconds < 600  # 10 minutes
                    
                    if is_active:
                        # Light mode is active, so stop it
                        success = await self._coordinator.client.async_stop_light_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully stopped light mode for tracker {self._tracker_id}")
                            # Trigger immediate coordinator update
                            await self._coordinator.async_request_refresh()
                        else:
                            raise HomeAssistantError(f"Failed to stop light mode for tracker {self._tracker_id}")
                    else:
                        # Timer expired, start new light mode
                        success = await self._coordinator.client.async_start_light_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully started light mode for tracker {self._tracker_id}")
                            # Immediately switch to fast polling and trigger update
                            _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_set_fast_polling()
                            _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_request_refresh()
                            _LOGGER.debug("Requested immediate refresh after starting light mode")
                        else:
                            raise HomeAssistantError(f"Failed to start light mode for tracker {self._tracker_id}")
                except (ValueError, TypeError):
                    # Invalid timer, start new light mode
                    success = await self._coordinator.client.async_start_light_mode(str(self._tracker_id))
                    if success:
                        _LOGGER.info(f"Successfully started light mode for tracker {self._tracker_id}")
                        # Immediately switch to fast polling and trigger update
                        _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_set_fast_polling()
                        _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_request_refresh()
                        _LOGGER.debug("Requested immediate refresh after starting light mode")
                    else:
                        raise HomeAssistantError(f"Failed to start light mode for tracker {self._tracker_id}")
            else:
                # Light mode is not active, so start it
                success = await self._coordinator.client.async_start_light_mode(str(self._tracker_id))
                if success:
                    _LOGGER.info(f"Successfully started light mode for tracker {self._tracker_id}")
                    # Immediately switch to fast polling and trigger update
                    _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                    await self._coordinator.async_set_fast_polling()
                    _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                    await self._coordinator.async_request_refresh()
                    _LOGGER.debug("Requested immediate refresh after starting light mode")
                else:
                    raise HomeAssistantError(f"Failed to start light mode for tracker {self._tracker_id}")
        except Exception as e:
            _LOGGER.error(f"Error controlling light mode for tracker {self._tracker_id}: {e}")
            raise HomeAssistantError(f"Error controlling light mode: {e}")

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


class PawfitAlarmModeButton(ButtonEntity):
    """Button to activate/deactivate Alarm Mode."""
    
    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker Alarm Mode"
        self._attr_unique_id = f"{tracker['petId']}_alarm_mode_button"
        self._attr_icon = "mdi:alarm-light"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit"
        }

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            # Check if alarm mode is currently active
            data = self._coordinator.data.get(str(self._tracker_id), {}) if self._coordinator.data else {}
            alarm_timer = data.get("alarm_timer", 0)
            
            if alarm_timer and alarm_timer > 0:
                # Check if within 10 minutes (active)
                import time
                try:
                    # Timer values from API are in milliseconds, convert to seconds
                    timer_start_seconds = alarm_timer / 1000.0
                    current_time_seconds = time.time()
                    elapsed_seconds = current_time_seconds - timer_start_seconds
                    is_active = elapsed_seconds < 600  # 10 minutes
                    
                    if is_active:
                        # Alarm mode is active, so stop it
                        success = await self._coordinator.client.async_stop_alarm_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully stopped alarm mode for tracker {self._tracker_id}")
                            # Trigger immediate coordinator update
                            await self._coordinator.async_request_refresh()
                        else:
                            raise HomeAssistantError(f"Failed to stop alarm mode for tracker {self._tracker_id}")
                    else:
                        # Timer expired, start new alarm mode
                        success = await self._coordinator.client.async_start_alarm_mode(str(self._tracker_id))
                        if success:
                            _LOGGER.info(f"Successfully started alarm mode for tracker {self._tracker_id}")
                            # Immediately switch to fast polling and trigger update
                            _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_set_fast_polling()
                            _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                            await self._coordinator.async_request_refresh()
                            _LOGGER.debug("Requested immediate refresh after starting alarm mode")
                        else:
                            raise HomeAssistantError(f"Failed to start alarm mode for tracker {self._tracker_id}")
                except (ValueError, TypeError):
                    # Invalid timer, start new alarm mode
                    success = await self._coordinator.client.async_start_alarm_mode(str(self._tracker_id))
                    if success:
                        _LOGGER.info(f"Successfully started alarm mode for tracker {self._tracker_id}")
                        # Immediately switch to fast polling and trigger update
                        _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_set_fast_polling()
                        _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                        await self._coordinator.async_request_refresh()
                        _LOGGER.debug("Requested immediate refresh after starting alarm mode")
                    else:
                        raise HomeAssistantError(f"Failed to start alarm mode for tracker {self._tracker_id}")
            else:
                # Alarm mode is not active, so start it
                success = await self._coordinator.client.async_start_alarm_mode(str(self._tracker_id))
                if success:
                    _LOGGER.info(f"Successfully started alarm mode for tracker {self._tracker_id}")
                    # Immediately switch to fast polling and trigger update
                    _LOGGER.debug(f"Before async_set_fast_polling: interval = {self._coordinator.update_interval}")
                    await self._coordinator.async_set_fast_polling()
                    _LOGGER.debug(f"After async_set_fast_polling: interval = {self._coordinator.update_interval}")
                    await self._coordinator.async_request_refresh()
                    _LOGGER.debug("Requested immediate refresh after starting alarm mode")
                else:
                    raise HomeAssistantError(f"Failed to start alarm mode for tracker {self._tracker_id}")
        except Exception as e:
            _LOGGER.error(f"Error controlling alarm mode for tracker {self._tracker_id}: {e}")
            raise HomeAssistantError(f"Error controlling alarm mode: {e}")

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
    """Set up Pawfit button entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for tracker in coordinator.trackers:
        entities.append(PawfitFindModeButton(tracker, coordinator))
        entities.append(PawfitLightModeButton(tracker, coordinator))
        entities.append(PawfitAlarmModeButton(tracker, coordinator))
    
    async_add_entities(entities)
