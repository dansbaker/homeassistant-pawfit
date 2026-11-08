"""Pawfit mode controls; ordinary refreshes never switch to fast polling."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from .const import DOMAIN


class PawfitModeButton(ButtonEntity):
    mode = "find"
    mode_icon = "mdi:crosshairs-gps"

    def __init__(self, tracker, coordinator):
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker {self.mode.title()} Mode"
        self._attr_unique_id = f"{tracker['petId']}_{self.mode}_mode_button"
        self._attr_icon = self.mode_icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
        }

    @property
    def available(self):
        return self._coordinator.tracker_available(self._tracker_id)

    async def async_press(self):
        await self._coordinator.async_toggle_mode(self._tracker_id, self.mode)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self):
        self.async_write_ha_state()


class PawfitFindModeButton(PawfitModeButton):
    mode = "find"


class PawfitLightModeButton(PawfitModeButton):
    mode = "light"
    mode_icon = "mdi:flashlight"


class PawfitAlarmModeButton(PawfitModeButton):
    mode = "alarm"
    mode_icon = "mdi:alarm-light"


class PawfitLocateButton(ButtonEntity):
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._attr_name = "PawFit Locate"
        self._attr_unique_id = f"{entry_id}_locate"

    @property
    def available(self):
        return self._coordinator.last_update_success

    async def async_press(self):
        await self._coordinator.async_locate()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [PawfitLocateButton(coordinator, entry.entry_id)]
    for tracker in coordinator.trackers:
        entities.extend(
            cls(tracker, coordinator)
            for cls in (
                PawfitFindModeButton,
                PawfitLightModeButton,
                PawfitAlarmModeButton,
            )
        )
    async_add_entities(entities)
