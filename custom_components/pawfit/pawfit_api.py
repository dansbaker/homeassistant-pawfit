"""Async client for Pawfit API authentication."""
from __future__ import annotations

import base64
import json
import logging
import zlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .const import BASE_URL, USER_AGENT
from .exceptions import (
    PawfitApiError,
    PawfitAuthenticationError,
    PawfitConnectionError,
    PawfitInvalidResponseError,
    PawfitNotAuthenticatedError,
)


class PawfitApiClient:
    """Async client for Pawfit API."""

    def __init__(
        self, 
        username: str, 
        password: str, 
        session: aiohttp.ClientSession
    ) -> None:
        """Initialize the Pawfit API client.
        
        Args:
            username: Pawfit account username
            password: Pawfit account password
            session: aiohttp client session
        """
        self._username = username
        self._password = password
        self._session = session
        self._token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._logger = logging.getLogger(__name__)

    async def async_login(self) -> Dict[str, str]:
        """Authenticate with Pawfit and return userId and sessionId.
        
        Returns:
            Dictionary containing userId and sessionId
            
        Raises:
            PawfitAuthenticationError: If authentication fails
            PawfitConnectionError: If connection fails
            PawfitInvalidResponseError: If response is invalid
        """
        # Build login URL with username and password as query parameters
        url = f"{BASE_URL}login/1/1"
        params = {"user": self._username, "pwd": self._password}
        headers = {"User-Agent": USER_AGENT}
        
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    self._logger.error(f"Pawfit login failed: status={resp.status}")
                    raise PawfitAuthenticationError(
                        "Incorrect username or password for Pawfit API"
                    )
                
                try:
                    # Try to parse as JSON, fallback to manual loads if mimetype is wrong
                    try:
                        data = await resp.json()
                    except Exception as e:
                        self._logger.warning(f"Falling back to manual JSON decode due to: {e}")
                        data = json.loads(resp_text)
                except json.JSONDecodeError as e:
                    self._logger.error(f"Failed to parse JSON from Pawfit login response: {e}")
                    raise PawfitInvalidResponseError("Invalid response from Pawfit API")
                
                data_field = data.get("data", {})
                user_id = data_field.get("userId")
                session_id = data_field.get("sessionId")
                
                if not user_id or not session_id:
                    self._logger.error("No userId or sessionId returned from Pawfit API")
                    raise PawfitAuthenticationError(
                        "No userId or sessionId returned from Pawfit API. Check your credentials."
                    )
                
                self._token = session_id
                self._user_id = user_id
                return {"userId": user_id, "sessionId": session_id}
                
        except aiohttp.ClientError as e:
            self._logger.error(f"Connection error during login: {e}")
            raise PawfitConnectionError(f"Failed to connect to Pawfit API: {e}")

    def _append_auth_to_url(self, url: str) -> str:
        """Append userId and sessionId to the URL as path parameters.
        
        Args:
            url: Base URL to append authentication to
            
        Returns:
            URL with authentication parameters appended
            
        Raises:
            PawfitNotAuthenticatedError: If client is not authenticated
        """
        # Use getattr to avoid AttributeError if not set
        user_id = getattr(self, "_user_id", None)
        token = getattr(self, "_token", None)
        if user_id is None or token is None:
            raise PawfitNotAuthenticatedError(
                "PawfitApiClient is not authenticated. Call async_login() first."
            )
        if url.endswith("/"):
            url = url[:-1]
        return f"{url}/{user_id}/{token}"

    async def _request_with_reauth(
        self, 
        method: str, 
        url: str, 
        headers: Dict[str, str], 
        append_auth: bool = True, 
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """Make a request with automatic re-authentication on 403 errors.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            append_auth: Whether to append authentication parameters
            **kwargs: Additional request parameters
            
        Returns:
            HTTP response object
            
        Raises:
            PawfitConnectionError: If connection fails
            PawfitApiError: If API request fails
        """
        if append_auth:
            url = self._append_auth_to_url(url)
        
        try:
            resp = await self._session.request(method, url, headers=headers, **kwargs)
            resp_text = await resp.text()
            
            if resp.status == 403:
                self._logger.warning("Pawfit API 403 received, attempting re-authentication.")
                login_data = await self.async_login()
                self._user_id = login_data["userId"]
                self._token = login_data["sessionId"]
                
                if append_auth:
                    # Rebuild URL with new authentication
                    original_url = url.split("/", 1)[0] if "/" in url else url
                    url = self._append_auth_to_url(original_url)
                
                resp = await self._session.request(method, url, headers=headers, **kwargs)
                
            return resp
            
        except aiohttp.ClientError as e:
            self._logger.error(f"Connection error during request: {e}")
            raise PawfitConnectionError(f"Failed to connect to Pawfit API: {e}")
        except Exception as e:
            self._logger.error(f"Unexpected error during request: {e}")
            raise PawfitApiError(f"Request failed: {e}")

    async def async_get_trackers(self) -> List[Dict[str, Any]]:
        """Fetch the list of tracker devices for the authenticated user.
        
        Returns:
            List of tracker dictionaries containing name, petId, and tracker_id
            
        Raises:
            PawfitNotAuthenticatedError: If client is not authenticated
            PawfitConnectionError: If connection fails
            PawfitInvalidResponseError: If response is invalid
        """
        # Ensure we are authenticated before making the request
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
            
        url = f"{BASE_URL}listpetinvitee/1/1"
        headers = {"User-Agent": USER_AGENT}
        
        try:
            resp = await self._request_with_reauth("GET", url, headers)
            resp_text = await resp.text()
            
            try:
                try:
                    data = await resp.json()
                except Exception as e:
                    self._logger.warning(f"Falling back to manual JSON decode for trackers due to: {e}")
                    data = json.loads(resp_text)
            except json.JSONDecodeError as e:
                self._logger.error(f"Failed to parse JSON from Pawfit trackers response: {e}, body={resp_text}")
                raise PawfitInvalidResponseError("Invalid response from Pawfit API (trackers)")
                
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
            
        except PawfitApiError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error fetching trackers: {e}")
            raise PawfitApiError(f"Failed to fetch trackers: {e}")

    async def async_get_locations(self, tracker_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch the latest location data for specified trackers.
        
        Args:
            tracker_ids: List of tracker IDs to fetch locations for
            
        Returns:
            Dictionary mapping tracker IDs to location data
            
        Raises:
            PawfitConnectionError: If connection fails
            PawfitInvalidResponseError: If response is invalid
        """
        url = f"{BASE_URL}getlocationcaches/1/1"
        headers = {"User-Agent": USER_AGENT}
        tracker_ids_str = ",".join(str(tid) for tid in tracker_ids)
        url = self._append_auth_to_url(url)
        url = f"{url}?trackers={tracker_ids_str}"
        
        self._logger.debug(f"Requesting locations: url={url}, headers={headers}, tracker_ids_str={tracker_ids_str}")
        
        try:
            resp = await self._request_with_reauth("GET", url, headers, append_auth=False)
            resp_text = await resp.text()
            self._logger.debug(f"Raw locations response: {resp_text}")
            self._logger.debug(f"Request details: method=GET, url={url}, headers={headers}, tracker_ids={tracker_ids}, response_status={resp.status}, response_text={resp_text}")
            
            try:
                data = json.loads(resp_text)
            except json.JSONDecodeError as e:
                self._logger.error(f"Failed to parse JSON from Pawfit locations response: {e}, body={resp_text}")
                self._logger.error(f"Request details for failed JSON parse: method=GET, url={url}, headers={headers}, tracker_ids={tracker_ids}, response_status={resp.status}, response_text={resp_text}")
                raise PawfitInvalidResponseError("Invalid response from Pawfit API (locations)")
                
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
            
        except PawfitApiError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error fetching locations: {e}")
            raise PawfitApiError(f"Failed to fetch locations: {e}")

    async def async_get_detailed_status(self, tracker_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get detailed status information for all trackers including timers.
        
        Args:
            tracker_ids: Optional list of tracker IDs to fetch status for
            
        Returns:
            Dictionary containing detailed status data for trackers
            
        Raises:
            PawfitConnectionError: If connection fails
            PawfitInvalidResponseError: If response is invalid
            PawfitApiError: If API returns failure
        """
        self._logger.debug(f"Starting async_get_detailed_status call with tracker_ids={tracker_ids}")
        
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            self._logger.debug("Not authenticated, calling async_login() before fetching detailed status")
            await self.async_login()
        
        url = f"{BASE_URL}getlocationcaches/1/1"
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # Add tracker IDs as query parameter if provided
            if tracker_ids:
                tracker_ids_str = ",".join(str(tid) for tid in tracker_ids)
                url = self._append_auth_to_url(url)
                url = f"{url}?trackers={tracker_ids_str}"
                self._logger.debug(f"Requesting detailed status: url={url}, headers={headers}, tracker_ids_str={tracker_ids_str}")
                resp = await self._request_with_reauth("GET", url, headers, append_auth=False)
            else:
                self._logger.debug(f"Requesting detailed status: url={url}, headers={headers}")
                resp = await self._request_with_reauth("GET", url, headers)
                
            resp_text = await resp.text()
            self._logger.debug(f"Raw detailed status response: {resp_text}")
            
            try:
                try:
                    data = await resp.json()
                except Exception as e:
                    self._logger.warning(f"Falling back to manual JSON decode for detailed status due to: {e}")
                    data = json.loads(resp_text)
            except json.JSONDecodeError as e:
                self._logger.error(f"Failed to parse JSON from detailed status response: {e}, body={resp_text}")
                raise PawfitInvalidResponseError("Invalid response from Pawfit API (detailed status)")
            
            self._logger.debug(f"Parsed detailed status JSON: {data}")
            
            if not data.get("success", False):
                self._logger.error(f"Detailed status API returned failure: {data}")
                raise PawfitApiError("Detailed status API returned failure")
            
            # Log the actual structure to help with debugging
            detailed_data = data.get("data", [])
            self._logger.debug(f"Detailed status data type: {type(detailed_data)}")
            
            if isinstance(detailed_data, dict):
                for tracker_id, tracker_data in detailed_data.items():
                    self._logger.debug(f"Tracker {tracker_id} detailed data keys: {list(tracker_data.keys()) if isinstance(tracker_data, dict) else 'Not a dict'}")
                    if isinstance(tracker_data, dict):
                        # Look for timer-related fields
                        timer_fields = {k: v for k, v in tracker_data.items() if 'timer' in k.lower()}
                        self._logger.debug(f"Tracker {tracker_id} timer fields: {timer_fields}")
            elif isinstance(detailed_data, list):
                for item in detailed_data:
                    if isinstance(item, dict):
                        self._logger.debug(f"List item keys: {list(item.keys())}")
                        timer_fields = {k: v for k, v in item.items() if 'timer' in k.lower()}
                        self._logger.debug(f"List item timer fields: {timer_fields}")
            
            return detailed_data
            
        except PawfitApiError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error fetching detailed status: {e}")
            raise PawfitApiError(f"Failed to fetch detailed status: {e}")

    async def async_start_find_mode(self, tracker_id: str) -> bool:
        """Start find mode for a specific tracker.
        
        Args:
            tracker_id: ID of the tracker to start find mode for
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            PawfitConnectionError: If connection fails
        """
        self._logger.debug(f"Starting find mode for tracker {tracker_id}")
        
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        url = f"{BASE_URL}starttracking/1/1"
        params = {"gps": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Starting find mode: url={url}, params={params}")
        
        try:
            resp = await self._request_with_reauth("GET", url, headers, params=params)
            resp_text = await resp.text()
            self._logger.debug(f"Find mode start response: status={resp.status}, body={resp_text}")
            
            if resp.status == 200:
                try:
                    data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                    return data.get("success", True)
                except Exception:
                    # If we can't parse JSON, assume success if status is 200
                    return True
            else:
                self._logger.error(f"Failed to start find mode: status={resp.status}, body={resp_text}")
                return False
                
        except PawfitConnectionError:
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error starting find mode: {e}")
            return False

    async def async_stop_find_mode(self, tracker_id: str) -> bool:
        """Stop find mode for a specific tracker.
        
        Args:
            tracker_id: ID of the tracker to stop find mode for
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            PawfitConnectionError: If connection fails
        """
        self._logger.debug(f"Stopping find mode for tracker {tracker_id}")
        
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        url = f"{BASE_URL}stoptracking/1/1"
        params = {"gps": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Stopping find mode: url={url}, params={params}")
        
        try:
            resp = await self._request_with_reauth("GET", url, headers, params=params)
            resp_text = await resp.text()
            self._logger.debug(f"Find mode stop response: status={resp.status}, body={resp_text}")
            
            if resp.status == 200:
                try:
                    data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                    return data.get("success", True)
                except Exception:
                    # If we can't parse JSON, assume success if status is 200
                    return True
            else:
                self._logger.error(f"Failed to stop find mode: status={resp.status}, body={resp_text}")
                return False
                
        except PawfitConnectionError:
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error stopping find mode: {e}")
            return False

    async def async_start_light_mode(self, tracker_id: str) -> bool:
        """Start light mode for a specific tracker."""
        self._logger.debug(f"Starting light mode for tracker {tracker_id}")
        # Note: This endpoint is assumed based on the pattern. May need adjustment.
        # If there's a specific light mode endpoint, update this URL accordingly.
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        # Using the same endpoint but with light=1 parameter instead of gps=1
        # This may need to be adjusted based on actual API documentation
        url = f"{BASE_URL}starttracking/1/1"
        params = {"light": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Starting light mode: url={url}, params={params}")
        
        resp = await self._request_with_reauth("GET", url, headers, params=params)
        resp_text = await resp.text()
        self._logger.debug(f"Light mode start response: status={resp.status}, body={resp_text}")
        
        if resp.status == 200:
            try:
                data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                return data.get("success", True)
            except:
                return True
        else:
            self._logger.error(f"Failed to start light mode: status={resp.status}, body={resp_text}")
            return False

    async def async_stop_light_mode(self, tracker_id: str) -> bool:
        """Stop light mode for a specific tracker."""
        self._logger.debug(f"Stopping light mode for tracker {tracker_id}")
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        url = f"{BASE_URL}stoptracking/1/1"
        params = {"light": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Stopping light mode: url={url}, params={params}")
        
        resp = await self._request_with_reauth("GET", url, headers, params=params)
        resp_text = await resp.text()
        self._logger.debug(f"Light mode stop response: status={resp.status}, body={resp_text}")
        
        if resp.status == 200:
            try:
                data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                return data.get("success", True)
            except:
                # If we can't parse JSON, assume success if status is 200
                return True
        else:
            self._logger.error(f"Failed to stop light mode: status={resp.status}, body={resp_text}")
            return False

    async def async_start_alarm_mode(self, tracker_id: str) -> bool:
        """Start alarm mode for a specific tracker."""
        self._logger.debug(f"Starting alarm mode for tracker {tracker_id}")
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        url = f"{BASE_URL}starttracking/1/1"
        params = {"speaker": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Starting alarm mode: url={url}, params={params}")
        
        resp = await self._request_with_reauth("GET", url, headers, params=params)
        resp_text = await resp.text()
        self._logger.debug(f"Alarm mode start response: status={resp.status}, body={resp_text}")
        
        if resp.status == 200:
            try:
                data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                return data.get("success", True)
            except:
                # If we can't parse JSON, assume success if status is 200
                return True
        else:
            self._logger.error(f"Failed to start alarm mode: status={resp.status}, body={resp_text}")
            return False

    async def async_stop_alarm_mode(self, tracker_id: str) -> bool:
        """Stop alarm mode for a specific tracker."""
        self._logger.debug(f"Stopping alarm mode for tracker {tracker_id}")
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        url = f"{BASE_URL}stoptracking/1/1"
        params = {"speaker": "1", "tracker": tracker_id}
        headers = {"User-Agent": USER_AGENT}
        
        self._logger.debug(f"Stopping alarm mode: url={url}, params={params}")
        
        resp = await self._request_with_reauth("GET", url, headers, params=params)
        resp_text = await resp.text()
        self._logger.debug(f"Alarm mode stop response: status={resp.status}, body={resp_text}")
        
        if resp.status == 200:
            try:
                data = await resp.json() if resp.content_type == 'application/json' else {"success": True}
                return data.get("success", True)
            except:
                # If we can't parse JSON, assume success if status is 200
                return True
        else:
            self._logger.error(f"Failed to stop alarm mode: status={resp.status}, body={resp_text}")
            return False

    async def async_get_activity_stats(self, tracker_id: str) -> Dict[str, Any]:
        """Get today's activity stats for a specific tracker.
        
        Args:
            tracker_id: ID of the tracker to get activity stats for
            
        Returns:
            Dictionary containing activity statistics
            
        Raises:
            PawfitConnectionError: If connection fails
        """
        self._logger.debug(f"Fetching activity stats for tracker {tracker_id}")
        
        # Ensure we are authenticated
        if not hasattr(self, "_user_id") or not hasattr(self, "_token") or self._user_id is None or self._token is None:
            await self.async_login()
        
        # Calculate today's date range (midnight to midnight)
        now = datetime.now()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_midnight = today_midnight.replace(hour=23, minute=59, second=59, microsecond=999000)
        
        # Convert to millisecond timestamps
        start_timestamp = int(today_midnight.timestamp() * 1000)
        end_timestamp = int(tomorrow_midnight.timestamp() * 1000)
        
        url = f"{BASE_URL}getactivitystatzip/1/1"
        headers = {"User-Agent": USER_AGENT}
        params = {
            "end": end_timestamp,
            "start": start_timestamp,
            "tracker": tracker_id
        }
        
        self._logger.debug(f"Activity stats request: url={url}, params={params}")
        self._logger.debug(f"Request parameters: start={start_timestamp} ({datetime.fromtimestamp(start_timestamp/1000)}), end={end_timestamp} ({datetime.fromtimestamp(end_timestamp/1000)}), tracker={tracker_id}")
        
        try:
            resp = await self._request_with_reauth("GET", url, headers, params=params)
            resp_text = await resp.text()
            
            self._logger.debug(f"Activity stats response: status={resp.status}, content_length={len(resp_text)}")
            
            if resp.status == 200:
                self._logger.debug(f"Raw response text (first 200 chars): {resp_text[:200]}...")
                
                # Decode the compressed response
                try:
                    decoded = zlib.decompress(base64.urlsafe_b64decode(resp_text + '=='))
                    self._logger.debug(f"Decompressed data length: {len(decoded)} bytes")
                    
                    raw_data = json.loads(decoded)
                    self._logger.debug(f"Parsed JSON keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'Not a dict'}")
                    
                    # Compile daily stats
                    stats = self._compile_daily_activity_stats(raw_data)
                    self._logger.info(f"Activity stats for tracker {tracker_id}: {stats}")
                    return stats
                    
                except Exception as decode_error:
                    self._logger.error(f"Failed to decode activity stats response: {decode_error}")
                    self._logger.debug(f"Raw response for debugging: {resp_text}")
                    return {"total_steps": 0, "total_calories": 0.0, "total_active_hours": 0.0}
            else:
                self._logger.error(f"Failed to fetch activity stats: status={resp.status}, body={resp_text}")
                return {"total_steps": 0, "total_calories": 0.0, "total_active_hours": 0.0}
                
        except Exception as e:
            self._logger.error(f"Error fetching activity stats for tracker {tracker_id}: {e}")
            return {"total_steps": 0, "total_calories": 0.0, "total_active_hours": 0.0}
    
    def _compile_daily_activity_stats(self, activity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compile hourly stats into daily summaries.
        
        Args:
            activity_data: Raw activity data from API
            
        Returns:
            Dictionary containing compiled daily statistics
        """
        self._logger.debug(f"Compiling activity data: {activity_data}")
        
        activities = activity_data.get('data', {}).get('activities', [])
        self._logger.debug(f"Found {len(activities)} daily activity entries")
        
        # Initialize totals
        total_steps = 0
        total_calories = 0.0
        total_active_hours = 0.0
        
        for i, day_activity in enumerate(activities):
            self._logger.debug(f"Processing day {i}: {day_activity}")
            hourly_stats = day_activity.get('hourlyStats', [])
            self._logger.debug(f"Day {i} has {len(hourly_stats)} hourly stats")
            
            for j, hour_stat in enumerate(hourly_stats):
                # Log each hour's data
                calorie = hour_stat.get('calorie', 0.0)
                active = hour_stat.get('active', 0.0)
                pace = hour_stat.get('pace', 0)
                
                self._logger.debug(f"Hour {j}: calorie={calorie}, active={active}, pace={pace}")
                
                # Sum up the totals
                total_calories += calorie
                total_active_hours += active
                total_steps += pace
        
        final_stats = {
            "total_steps": total_steps,
            "total_calories": round(total_calories, 2),
            "total_active_hours": round(total_active_hours, 2)
        }
        
        self._logger.debug(f"Final compiled stats: {final_stats}")
        return final_stats

