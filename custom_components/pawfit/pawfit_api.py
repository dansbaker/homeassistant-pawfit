"""Async client for Pawfit API authentication."""
import aiohttp
import logging
from .const import BASE_URL, USER_AGENT

class PawfitApiClient:
    def __init__(self, username: str, password: str, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None
        self._logger = logging.getLogger(__name__)

    async def async_login(self) -> dict:
        """Authenticate with Pawfit and return userId and sessionId. Raise on failure."""
        # Build login URL with username and password as query parameters
        url = BASE_URL + "login/1/1"
        params = {"user": self._username, "pwd": self._password}
        headers = {"User-Agent": USER_AGENT}
        self._logger.debug(f"Pawfit login request: url={url}, params={params}, headers={headers}")
        async with self._session.get(url, params=params, headers=headers) as resp:
            self._logger.debug(f"Pawfit login raw response headers: {dict(resp.headers)}")
            resp_text = await resp.text()
            self._logger.debug(f"Pawfit login response: status={resp.status}, body={resp_text}")
            if resp.status != 200:
                self._logger.error(f"Pawfit login failed: status={resp.status}, body={resp_text}")
                raise Exception("Incorrect username or password for Pawfit API")
            try:
                # Try to parse as JSON, fallback to manual loads if mimetype is wrong
                try:
                    data = await resp.json()
                except Exception as e:
                    self._logger.warning(f"Falling back to manual JSON decode due to: {e}")
                    import json
                    data = json.loads(resp_text)
            except Exception as e:
                self._logger.error(f"Failed to parse JSON from Pawfit login response: {e}, body={resp_text}")
                raise Exception("Invalid response from Pawfit API")
            self._logger.debug(f"Pawfit login parsed JSON: {data}")
            data_field = data.get("data", {})
            user_id = data_field.get("userId")
            session_id = data_field.get("sessionId")
            self._logger.debug(f"Extracted userId={user_id}, sessionId={session_id} from login response")
            if not user_id or not session_id:
                self._logger.error(f"No userId or sessionId returned from Pawfit API. data_field={data_field}")
                raise Exception("No userId or sessionId returned from Pawfit API. Check your credentials.")
            self._token = session_id
            self._user_id = user_id
            return {"userId": user_id, "sessionId": session_id}

    def _append_auth_to_url(self, url: str) -> str:
        """Append userId and sessionId to the URL as path parameters."""
        # Use getattr to avoid AttributeError if not set
        user_id = getattr(self, "_user_id", None)
        token = getattr(self, "_token", None)
        if user_id is None or token is None:
            raise Exception("PawfitApiClient is not authenticated. Call async_login() first.")
        if url.endswith("/"):
            url = url[:-1]
        return f"{url}/{user_id}/{token}"

    async def _request_with_reauth(self, method, url, headers, append_auth=True, **kwargs):
        if append_auth:
            url = self._append_auth_to_url(url)
        self._logger.debug(f"Pawfit API request: method={method}, url={url}, headers={headers}, kwargs={kwargs}")
        resp = await self._session.request(method, url, headers=headers, **kwargs)
        resp_text = await resp.text()
        self._logger.debug(f"Pawfit API response: status={resp.status}, body={resp_text}")
        if resp.status == 403:
            self._logger.warning("Pawfit API 403 received, attempting re-authentication.")
            login_data = await self.async_login()
            self._user_id = login_data["userId"]
            self._token = login_data["sessionId"]
            if append_auth:
                url = self._append_auth_to_url(url.split("/", 1)[0])
            self._logger.debug(f"Retrying Pawfit API request after re-auth: method={method}, url={url}, headers={headers}, kwargs={kwargs}")
            resp = await self._session.request(method, url, headers=headers, **kwargs)
            resp_text = await resp.text()
            self._logger.debug(f"Pawfit API retry response: status={resp.status}, body={resp_text}")
        return resp

    async def async_get_trackers(self) -> list:
        """Fetch the list of tracker devices for the authenticated user."""
        self._logger.debug("Starting async_get_trackers call")
        # Ensure we are authenticated before making the request
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            self._logger.debug("Not authenticated, calling async_login() before fetching trackers")
            await self.async_login()
        url = f"{BASE_URL}listpetinvitee/1/1"
        headers = {"User-Agent": USER_AGENT}
        self._logger.debug(f"Requesting tracker list: url={url}, headers={headers}")
        resp = await self._request_with_reauth("GET", url, headers)
        resp_text = await resp.text()
        self._logger.debug(f"Raw tracker list response: {resp_text}")
        try:
            try:
                data = await resp.json()
            except Exception as e:
                self._logger.warning(f"Falling back to manual JSON decode for trackers due to: {e}")
                import json
                data = json.loads(resp_text)
        except Exception as e:
            self._logger.error(f"Failed to parse JSON from Pawfit trackers response: {e}, body={resp_text}")
            raise Exception("Invalid response from Pawfit API (trackers)")
        self._logger.debug(f"Parsed tracker list JSON: {data}")
        trackers = []
        data_field = data.get("data", {})
        self._logger.debug(f"Trackers data_field type: {type(data_field)}, value: {data_field}")
        if isinstance(data_field, dict):
            for tracker_id, item in data_field.items():
                self._logger.debug(f"Processing tracker dict item: tracker_id={tracker_id}, item={item}")
                name = item.get("name")
                pet_id = item.get("petId")
                if name and pet_id is not None and tracker_id is not None:
                    trackers.append({"name": name, "petId": pet_id, "tracker_id": tracker_id})
        elif isinstance(data_field, list):
            for item in data_field:
                self._logger.debug(f"Processing tracker list item: {item}")
                tracker_id = item.get("tracker_id")
                if tracker_id is None:
                    tracker_id = item.get("id")
                if tracker_id is None:
                    tracker_id = item.get("trackerId")
                name = item.get("name")
                pet_id = item.get("petId")
                self._logger.debug(f"Extracted tracker_id={tracker_id}, name={name}, pet_id={pet_id}")
                if name is not None and pet_id is not None and tracker_id is not None:
                    trackers.append({"name": name, "petId": pet_id, "tracker_id": tracker_id})
        else:
            self._logger.error(f"Unexpected data type for trackers: {type(data_field)}. data_field={data_field}")
        self._logger.debug(f"Returning trackers: {trackers}")
        return trackers

    async def async_get_locations(self, tracker_ids: list) -> dict:
        """Fetch the latest location data for specified trackers."""
        self._logger.debug(f"Starting async_get_locations for tracker_ids={tracker_ids}")
        url = f"{BASE_URL}getlocationcaches/1/1"
        headers = {"User-Agent": USER_AGENT}
        tracker_ids_str = ",".join(str(tid) for tid in tracker_ids)
        url = self._append_auth_to_url(url)
        url = f"{url}?trackers={tracker_ids_str}"
        self._logger.debug(f"Requesting locations: url={url}, headers={headers}, tracker_ids_str={tracker_ids_str}")
        resp = await self._request_with_reauth("GET", url, headers, append_auth=False)
        resp_text = await resp.text()
        self._logger.debug(f"Raw locations response: {resp_text}")
        self._logger.debug(f"Request details: method=GET, url={url}, headers={headers}, tracker_ids={tracker_ids}, response_status={resp.status}, response_text={resp_text}")
        try:
            import json
            data = json.loads(resp_text)
        except Exception as e:
            self._logger.error(f"Failed to parse JSON from Pawfit locations response: {e}, body={resp_text}")
            self._logger.error(f"Request details for failed JSON parse: method=GET, url={url}, headers={headers}, tracker_ids={tracker_ids}, response_status={resp.status}, response_text={resp_text}")
            raise Exception("Invalid response from Pawfit API (locations)")
        self._logger.debug(f"Parsed locations JSON: {data}")
        locations = {}
        data_field = data.get("data", {})
        self._logger.debug(f"Locations data_field type: {type(data_field)}, value: {data_field}")
        if isinstance(data_field, dict):
            for tracker_id, loc in data_field.items():
                self._logger.debug(f"Processing location for tracker_id={tracker_id}, loc={loc}")
                state = loc.get("state", {})
                location = state.get("location", {})
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                accuracy = location.get("accuracy")
                last_update = state.get("utcDateTime")
                battery = state.get("power")
                signal = state.get("signal")
                locations[tracker_id] = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "accuracy": accuracy,
                    "last_update": last_update,
                    "battery": battery,
                    "signal": signal,
                    "_raw": loc
                }
        elif isinstance(data_field, list):
            for loc in data_field:
                self._logger.debug(f"Processing location list item: {loc}")
                tracker_id = loc.get("tracker")
                if tracker_id is None:
                    tracker_id = loc.get("tracker_id")
                if tracker_id is None:
                    tracker_id = loc.get("id")
                if tracker_id is None:
                    tracker_id = loc.get("trackerId")
                state = loc.get("state", {})
                location = state.get("location", {})
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                accuracy = location.get("accuracy")
                last_update = state.get("utcDateTime")
                battery = state.get("power")
                signal = state.get("signal")
                if tracker_id is not None:
                    locations[tracker_id] = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "accuracy": accuracy,
                        "last_update": last_update,
                        "battery": battery,
                        "signal": signal,
                        "_raw": loc
                    }
        else:
            self._logger.error(f"Unexpected data type for locations: {type(data_field)}. data_field={data_field}")
        self._logger.debug(f"Returning locations: {locations}")
        return locations

