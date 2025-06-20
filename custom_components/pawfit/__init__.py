"""The Pawfit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pawfit from a config entry."""
    # Await the platform setup to ensure proper setup lock handling
    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker"])
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Pawfit integration (empty for UI-only)."""
    return True
