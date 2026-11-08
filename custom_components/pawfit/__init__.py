"""The Pawfit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .pawfit_api import PawfitApiClient
from .device_tracker import PawfitDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pawfit from a config entry."""
    # Create the API client. Fork change: HA's shared HTTP session (upstream
    # opened a new one on every setup and never closed it), and HA's clock
    # for the daily request count.
    client = PawfitApiClient(
        entry.data["username"],
        entry.data["password"],
        async_get_clientsession(hass),
        now_fn=dt_util.now,
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
