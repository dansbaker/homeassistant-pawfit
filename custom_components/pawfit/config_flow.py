"""Config flow for Pawfit integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .exceptions import PawfitAuthenticationError, PawfitConnectionError
from .pawfit_api import PawfitApiClient


class PawfitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pawfit."""

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step.
        
        Args:
            user_input: Form input data
            
        Returns:
            Configuration flow result
        """
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Validate credentials with Pawfit API
            async with aiohttp.ClientSession() as session:
                client = PawfitApiClient(
                    user_input["username"], 
                    user_input["password"], 
                    session
                )
                try:
                    login_data = await client.async_login()
                except PawfitAuthenticationError:
                    errors["base"] = "invalid_auth"
                except PawfitConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    errors["base"] = "unknown"
                else:
                    # Store username, password, userId, and sessionId in config entry
                    entry_data = {
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "userId": login_data["userId"],
                        "sessionId": login_data["sessionId"],
                    }
                    return self.async_create_entry(
                        title="Pawfit Account", 
                        data=entry_data
                    )
                    
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
        )
