"""Async client for Pawfit API authentication."""

import asyncio
import base64
import json
import math
import zlib
import aiohttp
import hashlib
import logging
import time
from datetime import datetime, timedelta
from .const import BASE_URL, USER_AGENT, REQUEST_TIMEOUT_SECONDS

from .exceptions import (
    PawfitApiError,
    PawfitAuthenticationError,
    PawfitConnectionError,
    PawfitInvalidResponseError,
    PawfitRateLimitError,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)

# Secret key extracted from Pawfit Android APK v3.3.0
# Located in com.latsen.pawfit.common.base.Const.g()
PAWFIT_SECRET = "ldjou32rweo$#runvjvn@!pzm"


def _sha256_hex(data: str) -> str:
    """Calculate SHA-256 hash and return as lowercase hex string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def calculate_login_sign(account: str, password: str, timestamp: int) -> str:
    """
    Calculate the 'sign' parameter for login requests.

    Formula: SHA256(timestamp + account + password + SECRET)
    """
    data = f"{timestamp}{account}{password}{PAWFIT_SECRET}"
    return _sha256_hex(data)


def calculate_api_sign(
    user_id: str,
    session_id: str,
    identity: str = "",
    target: str = "",
    tracker: str = "",
    pet: str = "",
) -> str:
    """
    Calculate the 'sign' parameter for authenticated API requests.

    Formula: SHA256(sessionId + userId + identity + target + tracker + pet + SECRET)
    """
    data = f"{session_id}{user_id}{identity}{target}{tracker}{pet}{PAWFIT_SECRET}"
    return _sha256_hex(data)


class PawfitApiClient:
    """Bounded, signed requests with one token refresh and no private payload logging."""

    def __init__(self, username, password, session, now_fn=None):
        self._username = username
        self._password = password
        self._session = session
        self._token = None
        self._user_id = None
        self._auth_lock = asyncio.Lock()
        self._logger = logging.getLogger(__name__)
        self._now = now_fn or datetime.now
        self.counting_since = self._now()
        self._count_day = self.counting_since.date()
        self.request_count = 0
        self.requests_today = 0
        self.last_request = None

    def _count_request(self):
        now = self._now()
        if now.date() != self._count_day:
            self._count_day = now.date()
            self.requests_today = 0
            self.counting_since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self.request_count += 1
        self.requests_today += 1
        self.last_request = now

    async def async_login(self):
        async with self._auth_lock:
            return await self._async_login_unlocked()

    async def _async_login_unlocked(self):
        timestamp = int(time.time() * 1000)
        form = {
            "user": self._username,
            "pwd": self._password,
            "t": str(timestamp),
            "sign": calculate_login_sign(self._username, self._password, timestamp),
        }
        self._count_request()
        try:
            async with self._session.post(
                BASE_URL + "login/1/1",
                data=form,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                self._check_status(response.status)
                data = self._decode_json(await self._read_text(response))
        except (aiohttp.ClientError, TimeoutError):
            raise PawfitConnectionError("Pawfit login connection failed") from None
        if data.get("success") is not True:
            raise PawfitAuthenticationError("Pawfit rejected the login")
        payload = data.get("data")
        if (
            not isinstance(payload, dict)
            or not payload.get("userId")
            or not payload.get("sessionId")
        ):
            raise PawfitInvalidResponseError(
                "Pawfit login response is missing account/session fields"
            )
        self._user_id = str(payload["userId"])
        self._token = str(payload["sessionId"])
        return {"userId": self._user_id, "sessionId": self._token}

    async def _async_reauthenticate(self, previous_token):
        async with self._auth_lock:
            if self._token == previous_token:
                await self._async_login_unlocked()

    @staticmethod
    def _check_status(status):
        if status in (401, 403):
            raise PawfitAuthenticationError("Pawfit authentication rejected")
        if status == 429:
            raise PawfitRateLimitError("Pawfit rate limit reached")
        if not 200 <= status < 300:
            raise PawfitApiError(f"Pawfit HTTP status {status}")

    @staticmethod
    async def _read_text(response):
        try:
            return await response.text()
        except (aiohttp.ClientError, TimeoutError):
            raise PawfitConnectionError("Pawfit response connection failed") from None

    @staticmethod
    def _decode_json(text):
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            raise PawfitInvalidResponseError("Pawfit returned invalid JSON") from None
        if not isinstance(data, dict):
            raise PawfitInvalidResponseError("Pawfit response must be an object")
        return data

    def _append_auth_to_url(self, url):
        if self._user_id is None or self._token is None:
            raise PawfitAuthenticationError("Pawfit login is required")
        return f"{url.rstrip('/')}/{self._user_id}/{self._token}"

    def _get_sign(self, tracker="", identity="", target="", pet=""):
        if self._user_id is None or self._token is None:
            raise PawfitAuthenticationError("Pawfit login is required")
        return calculate_api_sign(
            str(self._user_id), str(self._token), identity, target, tracker, pet
        )

    def _add_sign_to_params(self, params=None, **sign_params):
        return {**(params or {}), "sign": self._get_sign(**sign_params)}

    async def _request_with_reauth(
        self, method, url, headers, append_auth=True, sign_params=None, **kwargs
    ):
        if self._token is None:
            await self._async_reauthenticate(None)
        # Keep the unauthenticated base URL and parameters for BOTH attempts.
        # Auth paths and signatures must be rebuilt after token renewal.
        original_params = dict(kwargs.pop("params", {}) or {})
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)

        async def request_once():
            request_url = self._append_auth_to_url(url) if append_auth else url
            params = self._add_sign_to_params(original_params, **(sign_params or {}))
            self._count_request()
            try:
                return await self._session.request(
                    method, request_url, headers=headers, params=params, **kwargs
                )
            except (aiohttp.ClientError, TimeoutError):
                raise PawfitConnectionError(
                    "Pawfit request connection failed"
                ) from None

        token = self._token
        response = await request_once()
        if response.status in (401, 403):
            response.release()
            await self._async_reauthenticate(token)
            response = await request_once()
        try:
            self._check_status(response.status)
        except (PawfitApiError, PawfitAuthenticationError, PawfitRateLimitError):
            response.release()
            raise
        return response

    async def _json_request(self, endpoint, params=None, sign_params=None):
        response = await self._request_with_reauth(
            "GET",
            BASE_URL + endpoint + "/1/1",
            {"User-Agent": USER_AGENT},
            params=params,
            sign_params=sign_params,
        )
        try:
            data = self._decode_json(await self._read_text(response))
            if data.get("success") is not True:
                raise PawfitApiError("Pawfit reported an unsuccessful request")
            return data.get("data")
        finally:
            response.release()

    @staticmethod
    def _records(data):
        if isinstance(data, dict):
            return data.items()
        if isinstance(data, list):
            return (
                (
                    next(
                        (
                            item[k]
                            for k in ("tracker", "tracker_id", "id", "trackerId")
                            if item.get(k) is not None
                        ),
                        None,
                    ),
                    item,
                )
                for item in data
                if isinstance(item, dict)
            )
        raise PawfitInvalidResponseError("Pawfit returned an invalid device collection")

    async def async_get_trackers(self):
        payload = await self._json_request("listpetinvitee")
        trackers = []
        for tid, item in self._records(payload):
            if (
                not isinstance(item, dict)
                or tid is None
                or not item.get("name")
                or item.get("petId") is None
            ):
                continue
            trackers.append(
                {
                    "tracker_id": str(tid),
                    "petId": item["petId"],
                    "name": item["name"],
                    "model": item.get("model", "Unknown"),
                }
            )
        return trackers

    async def async_get_locations(self, tracker_ids):
        payload = await self._json_request(
            "getlocationcaches", {"trackers": ",".join(str(t) for t in tracker_ids)}
        )
        result = {}
        for tid, item in self._records(payload):
            if tid is None or not isinstance(item, dict):
                continue
            state = item.get("state")
            if not isinstance(state, dict):
                continue
            location = state.get("location")
            if not isinstance(location, dict):
                location = {}
            result[str(tid)] = {
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "accuracy": location.get("accuracy"),
                "last_update": location.get("utcDateTime"),
                "battery": state.get("power"),
                "signal": state.get("signal"),
                "_raw": item,
            }
        return result

    async def async_get_detailed_status(self, tracker_ids=None):
        params = (
            {"trackers": ",".join(str(t) for t in tracker_ids)} if tracker_ids else None
        )
        return await self._json_request("getlocationcaches", params)

    async def _async_mode(self, tracker_id, field, enabled):
        response = await self._request_with_reauth(
            "GET",
            BASE_URL + ("starttracking" if enabled else "stoptracking") + "/1/1",
            {"User-Agent": USER_AGENT},
            params={field: "1", "tracker": str(tracker_id)},
            sign_params={"tracker": str(tracker_id)},
        )
        try:
            data = self._decode_json(await self._read_text(response))
            # A 200 with an error/malformed payload must not show a successful command.
            return data.get("success") is True
        finally:
            response.release()

    async def async_start_find_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "gps", True)

    async def async_stop_find_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "gps", False)

    async def async_start_light_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "light", True)

    async def async_stop_light_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "light", False)

    async def async_start_alarm_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "speaker", True)

    async def async_stop_alarm_mode(self, tracker_id):
        return await self._async_mode(tracker_id, "speaker", False)

    async def async_get_activity_stats(self, tracker_id):
        now = self._now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(milliseconds=1)
        response = await self._request_with_reauth(
            "GET",
            BASE_URL + "getactivitystatzip/1/1",
            {"User-Agent": USER_AGENT},
            params={
                "start": int(start.timestamp() * 1000),
                "end": int(end.timestamp() * 1000),
                "tracker": str(tracker_id),
            },
            sign_params={"tracker": str(tracker_id)},
        )
        try:
            text = await self._read_text(response)
            try:
                # Bound decompression; a malformed response must not exhaust memory.
                decoder = zlib.decompressobj()
                raw = decoder.decompress(
                    base64.urlsafe_b64decode(text + "=="), 2_000_000
                )
                if not decoder.eof:
                    raise ValueError("Incomplete/oversized activity response")
                data = self._decode_json(raw)
                return self._compile_daily_activity_stats(data)
            except (ValueError, TypeError, zlib.error):
                raise PawfitInvalidResponseError(
                    "Pawfit returned invalid activity data"
                ) from None
        finally:
            response.release()

    def _compile_daily_activity_stats(self, data):
        try:
            activities = data["data"]["activities"]
            if not isinstance(activities, list):
                raise TypeError
            hours = [hour for day in activities for hour in day.get("hourlyStats", [])]
            stats = {
                "total_steps": sum(int(h.get("pace", 0)) for h in hours),
                "total_calories": round(
                    sum(float(h.get("calorie", 0)) for h in hours), 2
                ),
                "total_active_hours": round(
                    sum(float(h.get("active", 0)) for h in hours), 2
                ),
            }
            if any(not math.isfinite(value) or value < 0 for value in stats.values()):
                raise ValueError
            return stats
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            raise PawfitInvalidResponseError(
                "Pawfit returned invalid activity statistics"
            ) from None
