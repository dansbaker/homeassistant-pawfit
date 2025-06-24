"""The Pawfit integration."""

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .pawfit_api import PawfitApiClient
from .device_tracker import PawfitDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pawfit from a config entry."""
    # Create the API client
    session = aiohttp.ClientSession()
    client = PawfitApiClient(
        entry.data["username"],
        entry.data["password"],
        session
    )
    
    # Get trackers and create coordinator
    trackers = await client.async_get_trackers()
    coordinator = PawfitDataUpdateCoordinator(hass, client, trackers)
    
    # Start the coordinator to begin polling
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in hass.data for platforms to use
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    # Forward the config entry setup to multiple platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker", "binary_sensor", "sensor", "button"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["device_tracker", "binary_sensor", "sensor", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Pawfit integration (empty for UI-only)."""
    return True
