# Placeholder for config flow implementation
# Will prompt for username and password, store session token

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
import aiohttp

from .const import DOMAIN
from .pawfit_api import PawfitApiClient

class PawfitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pawfit."""

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate credentials with Pawfit API
            async with aiohttp.ClientSession() as session:
                client = PawfitApiClient(user_input["username"], user_input["password"], session)
                try:
                    login_data = await client.async_login()
                except Exception:
                    errors["base"] = "auth"
                else:
                    # Store username, password, userId, and sessionId in config entry
                    entry_data = {
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "userId": login_data["userId"],
                        "sessionId": login_data["sessionId"],
                    }
                    return self.async_create_entry(title="Pawfit Account", data=entry_data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
        )
