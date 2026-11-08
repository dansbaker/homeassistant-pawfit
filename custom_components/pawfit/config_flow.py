"""UI setup and credential recovery for Pawfit accounts."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .pawfit_api import PawfitApiClient
from .exceptions import PawfitAuthenticationError, PawfitConnectionError, PawfitError


class PawfitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _login(self, user_input):
        client = PawfitApiClient(
            user_input["username"],
            user_input["password"],
            async_get_clientsession(self.hass),
        )
        return await client.async_login()

    async def async_step_user(self, user_input=None):
        return await self._credentials(user_input, False)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._credentials(user_input, True)

    async def _credentials(self, user_input, reauth):
        errors = {}
        if user_input is not None:
            try:
                login = await self._login(user_input)
            except PawfitAuthenticationError:
                errors["base"] = "invalid_auth"
            except PawfitConnectionError:
                errors["base"] = "cannot_connect"
            except PawfitError:
                errors["base"] = "invalid_response"
            else:
                account_id = str(login["userId"])
                if reauth:
                    entry = self._get_reauth_entry()
                    previous = entry.unique_id or entry.data.get("userId")
                    if previous is not None and str(previous) != account_id:
                        errors["base"] = "wrong_account"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates={**user_input, "userId": account_id},
                            reason="reauth_successful",
                        )
                else:
                    await self.async_set_unique_id(account_id)
                    self._abort_if_unique_id_configured()
                    if any(
                        e.data.get("username", "").strip().casefold()
                        == user_input["username"].strip().casefold()
                        for e in self._async_current_entries()
                    ):
                        return self.async_abort(reason="already_configured")
                    return self.async_create_entry(
                        title="Pawfit Account",
                        data={**user_input, "userId": account_id},
                    )
        default_user = (
            self._get_reauth_entry().data.get("username", "") if reauth else ""
        )
        return self.async_show_form(
            step_id="reauth_confirm" if reauth else "user",
            data_schema=vol.Schema(
                {
                    vol.Required("username", default=default_user): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
