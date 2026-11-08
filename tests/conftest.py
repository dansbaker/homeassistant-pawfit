"""Test fixtures: a fake Pawfit API that records every request it receives."""

import base64
import json
import re
import time
import zlib
from http import HTTPStatus

import pytest

# Import this repo's custom_components first, so the test harness's own
# testing_config/custom_components package doesn't shadow it.
import custom_components.pawfit  # noqa: F401
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

DOMAIN = "pawfit"
BASE = "https://pawfitapi.latsen.com/api/v1/"
TRACKERS = {
    "1001": {"name": "Tom", "petId": 11},
    "1002": {"name": "Ginger", "petId": 12},
}
ENDPOINTS = [
    ("login", "post"),
    ("listpetinvitee", "get"),
    ("getlocationcaches", "get"),
    ("getactivitystatzip", "get"),
    ("starttracking", "get"),
    ("stoptracking", "get"),
]
MODE_FIELDS = {"gps": "timerGps", "light": "timerLight", "speaker": "timerSpeaker"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakePawfit:
    """Answers the Pawfit endpoints and logs (endpoint, monotonic, unix time)."""

    def __init__(self, aioclient_mock):
        self.calls = []
        self.fail_next_location_with_403 = False
        self.location_hangs = False  # True: location requests time out
        # Each tracker's last position fix (seconds since epoch): old to start with.
        self.fix_times = {tid: 1790000000 for tid in TRACKERS}
        # In Find mode a tracker reports straight away, unless this is False (offline).
        self.reports_when_finding = True
        self.finding = {tid: False for tid in TRACKERS}
        self.timers = {tid: {} for tid in TRACKERS}
        for endpoint, method in ENDPOINTS:
            getattr(aioclient_mock, method)(
                re.compile(re.escape(BASE + endpoint + "/")),
                side_effect=self._handler(endpoint),
            )

    def _handler(self, endpoint):
        async def handler(method, url, data):
            self.calls.append((endpoint, time.monotonic(), time.time()))
            return self._respond(endpoint, method, url)

        return handler

    def _respond(self, endpoint, method, url):
        def ok(payload):
            return AiohttpClientMockResponse(method, url, json=payload)

        if endpoint == "login":
            return ok({"success": True, "data": {"userId": "u1", "sessionId": "s1"}})
        if endpoint == "listpetinvitee":
            return ok({"success": True, "data": TRACKERS})
        if endpoint == "getlocationcaches":
            if self.location_hangs:
                return AiohttpClientMockResponse(method, url, exc=TimeoutError())
            if self.fail_next_location_with_403:
                self.fail_next_location_with_403 = False
                return AiohttpClientMockResponse(method, url, status=HTTPStatus.FORBIDDEN, text="")
            return ok({"success": True, "data": {
                tid: {
                    "state": {
                        "location": {"latitude": 52.63, "longitude": 1.29, "accuracy": 12, "utcDateTime": self._fix(tid)},
                        "power": 80,
                        "signal": -70,
                    },
                    "model": "TR3",
                    **self.timers[tid],
                }
                for tid in TRACKERS
            }})
        if endpoint == "getactivitystatzip":
            body = {"data": {"activities": [{"hourlyStats": [{"calorie": 1.5, "active": 0.25, "pace": 120}]}]}}
            packed = base64.urlsafe_b64encode(zlib.compress(json.dumps(body).encode())).decode().rstrip("=")
            return AiohttpClientMockResponse(method, url, text=packed)
        if endpoint in ("starttracking", "stoptracking"):
            tid = url.query["tracker"]
            if url.query.get("gps") == "1":
                self.finding[tid] = endpoint == "starttracking"
            for param, field in MODE_FIELDS.items():
                if url.query.get(param) == "1":
                    self.timers[tid][field] = int(time.time() * 1000) if endpoint == "starttracking" else 0
            return ok({"success": True})
        raise AssertionError(endpoint)

    def _fix(self, tid):
        if self.finding[tid] and self.reports_when_finding:
            self.fix_times[tid] = int(time.time())
        return self.fix_times[tid]

    def count(self, endpoint):
        return sum(1 for c in self.calls if c[0] == endpoint)

    def times(self, endpoint):
        """Monotonic times of the calls to an endpoint."""
        return [c[1] for c in self.calls if c[0] == endpoint]

    def wall_times(self, endpoint):
        """Unix timestamps of the calls to an endpoint."""
        return [c[2] for c in self.calls if c[0] == endpoint]

    def since(self, index):
        return [c[0] for c in self.calls[index:]]


@pytest.fixture
def pawfit(aioclient_mock):
    return FakePawfit(aioclient_mock)


@pytest.fixture
async def setup_entry(hass, pawfit):
    await hass.config.async_set_time_zone("Europe/London")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pawfit Account",
        data={"username": "spare@example.com", "password": "pw", "userId": "u1", "sessionId": "s1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def advance(hass, freezer, seconds, step=1, each=None):
    """Move time forward in steps, firing every timer that falls due."""
    for _ in range(int(seconds / step)):
        freezer.tick(step)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        if each is not None:
            await each()
            await hass.async_block_till_done()
