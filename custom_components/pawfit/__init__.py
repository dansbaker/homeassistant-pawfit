"""The Pawfit integration."""
from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device_tracker import PawfitDataUpdateCoordinator
from .pawfit_api import PawfitApiClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pawfit from a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        
    Returns:
        True if setup was successful
    """
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
    await hass.config_entries.async_forward_entry_setups(
        entry, ["device_tracker", "binary_sensor", "sensor", "button"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        
    Returns:
        True if unload was successful
    """
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["device_tracker", "binary_sensor", "sensor", "button"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Pawfit integration (empty for UI-only).
    
    Args:
        hass: Home Assistant instance
        config: Integration configuration
        
    Returns:
        True if setup was successful
    """
    return True
