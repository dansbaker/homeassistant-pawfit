import asyncio
import math
import logging
import time
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .exceptions import PawfitAuthenticationError
from .helpers import charging, mode_remaining
from .const import (
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
    MIN_FETCH_SPACING_SECONDS,
    ACTIVITY_INTERVAL_SECONDS,
    KEEP_LAST_DATA_SECONDS,
    LOCATE_TIMEOUT_SECONDS,
    LOCATE_CLOCK_SLACK_SECONDS,
    STALE_AFTER_SECONDS,
)


def _mode_active(timer_ms):
    return mode_remaining(timer_ms) > 0


def fix_time(tracker_data):
    """When the tracker last reported its position (seconds since epoch), or None."""
    if not tracker_data:
        return None
    raw = tracker_data.get("_raw")
    if not isinstance(raw, dict) or not isinstance(raw.get("state"), dict):
        return None
    location = raw["state"].get("location")
    if not isinstance(location, dict):
        return None
    value = location.get("utcDateTime")
    try:
        value = float(value)
        if (
            not math.isfinite(value)
            or value <= 0
            or value > time.time() + LOCATE_CLOCK_SLACK_SECONDS
        ):
            return None
        dt_util.utc_from_timestamp(value)
        return value
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def coordinate(value, minimum, maximum):
    """Accept finite coordinates, including zero; reject malformed payload values."""
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and minimum <= value <= maximum else None
    except (TypeError, ValueError, OverflowError):
        return None


class PawfitDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch every tracker's data on a fixed schedule, with a hard rate limit.

    Fork change. Upstream polled every 60 s but switched to 1 s polling for
    10 minutes after any Find/Light/Alarm press, fetched activity on every
    refresh, and let any refresh request (homeassistant.update_entity, a
    button) trigger an extra fetch. Here:
    - location is fetched every UPDATE_INTERVAL_SECONDS, in one request for
      all trackers (upstream made the same request twice per refresh);
    - extra refresh requests are ignored until a minute has passed, and two
      fetches are never closer than MIN_FETCH_SPACING_SECONDS whatever asks;
    - daily activity is fetched at most every ACTIVITY_INTERVAL_SECONDS.
    """

    def __init__(self, hass, client, trackers):
        self.logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger=self.logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.trackers = trackers
        self.tracker_ids = [t["tracker_id"] for t in trackers]
        self._last_fetch = None  # time.monotonic() of the last location fetch
        self._activity = {}  # str(tracker_id) -> activity stats
        self._activity_fetched = None  # time.monotonic() of the last activity fetch
        self._activity_day = None
        self.fetches_today = 0
        self._fetch_day = None
        self._last_success = None  # time.monotonic() of the last good location fetch
        self._failing_since = (
            None  # time.monotonic() when the current failure streak began
        )
        # Locate (fork change): time.time() the current locate began, or None.
        self.locate_started = None
        # str(tracker_id) -> True if Locate turned Find mode on (so it turns it off).
        self._locate_pending = {}
        self._locate_baseline = {}
        self._locate_errors = []
        self._cleanup_pending = set()
        self._cleanup_attempts = {}
        self._locate_cancel = None
        self._locate_timeout_task = None
        self._command_lock = asyncio.Lock()
        self._tracker_success = {}
        self.locate_last_result = None
        self.locate_last_finished = None  # datetime (UTC)
        self.logger.info(
            f"PawfitDataUpdateCoordinator initialized with trackers: {self.tracker_ids}"
        )

    def _seconds_since_fetch(self):
        if self._last_fetch is None:
            return None
        return time.monotonic() - self._last_fetch

    async def async_request_refresh(self) -> None:
        """Ignore refresh requests within a minute of the last fetch.

        Covers homeassistant.update_entity and anything else that asks for a
        refresh outside the schedule. Dropping them here, not only in
        _async_update_data, also stops a skipped request from pushing the
        next scheduled fetch back.
        """
        since = self._seconds_since_fetch()
        if since is not None and since < UPDATE_INTERVAL_SECONDS:
            self.logger.debug(
                "Refresh request ignored: last Pawfit fetch %.0f s ago", since
            )
            return
        await super().async_request_refresh()

    @callback
    def async_set_mode_timer(self, tracker_id, key, value) -> None:
        """Record a Find/Light/Alarm change locally, without an extra fetch.

        The next scheduled fetch replaces it with what Pawfit reports.
        """
        if not self.data:
            return
        tracker_data = self.data.get(str(tracker_id))
        if tracker_data is None:
            return
        tracker_data[key] = value
        self.async_update_listeners()

    def tracker_name(self, tracker_id) -> str:
        for t in self.trackers:
            if str(t["tracker_id"]) == str(tracker_id):
                return t.get("name") or str(tracker_id)
        return str(tracker_id)

    @property
    def locate_waiting_for(self) -> list:
        return [self.tracker_name(tid) for tid in self._locate_pending]

    def tracker_available(self, tracker_id):
        return self.last_update_success and str(tracker_id) in (self.data or {})

    async def async_toggle_mode(self, tracker_id, mode):
        """Serialize user controls with Locate; user changes take ownership."""
        async with self._command_lock:
            tid = str(tracker_id)
            if not self.tracker_available(tid):
                raise HomeAssistantError("Tracker data is unavailable")
            key = mode + "_timer"
            active = _mode_active(self.data[tid].get(key))
            method = getattr(
                self.client, f"async_{'stop' if active else 'start'}_{mode}_mode"
            )
            try:
                success = await method(tid)
            except Exception:
                raise HomeAssistantError(
                    "Pawfit command could not be delivered"
                ) from None
            if not success:
                raise HomeAssistantError("Pawfit rejected the command")
            self.async_set_mode_timer(
                tid, key, 0 if active else int(time.time() * 1000)
            )
            if mode == "find":
                self._cleanup_pending.discard(tid)
                if tid in self._locate_pending:
                    self._locate_pending.pop(tid)
                    self._locate_errors.append(
                        "Manual Find change for " + self.tracker_name(tid)
                    )
                    if not self._locate_pending:
                        self._finish_locate()
            self.async_update_listeners()

    async def async_locate(self):
        async with self._command_lock:
            if self.locate_started is not None:
                return
            if self._cleanup_pending:
                raise HomeAssistantError(
                    "Find cleanup is pending; switch Find off before starting another Locate"
                )
            self.locate_started = time.time()
            self._locate_deadline = time.monotonic() + LOCATE_TIMEOUT_SECONDS
            self._locate_pending = {}
            self._locate_errors = []
            self._locate_baseline = {
                str(t): fix_time((self.data or {}).get(str(t)))
                for t in self.tracker_ids
            }
            for tracker_id in self.tracker_ids:
                tid = str(tracker_id)
                data = (self.data or {}).get(tid, {})
                if _mode_active(data.get("find_timer")):
                    self._locate_pending[tid] = False
                    continue
                try:
                    started = await self.client.async_start_find_mode(tid)
                except Exception:
                    started = False
                if not started:
                    self._locate_errors.append(
                        "Could not start Find for " + self.tracker_name(tid)
                    )
                    continue
                self._locate_pending[tid] = True
                if self.data and tid in self.data:
                    self.data[tid]["find_timer"] = int(time.time() * 1000)
            if not self._locate_pending:
                self._finish_locate()
                self.async_update_listeners()
                raise HomeAssistantError("Pawfit could not start Locate")

            @callback
            def timeout(_now):
                self._locate_timeout_task = self.hass.async_create_task(
                    self._async_locate_timeout()
                )

            self._locate_cancel = async_call_later(
                self.hass, max(0, self._locate_deadline - time.monotonic()), timeout
            )
            self.async_update_listeners()

    async def _async_locate_timeout(self):
        await self._async_check_locate(self.data, force_timeout=True)
        self.async_update_listeners()

    async def _async_check_locate(self, location_data, force_timeout=False):
        async with self._command_lock:
            # Retry failed cleanup only a bounded number of times; never claim
            # the tracker stopped until the API acknowledges it.
            for tid in list(self._cleanup_pending):
                if self._cleanup_attempts.get(tid, 0) < 3:
                    self._cleanup_attempts[tid] = self._cleanup_attempts.get(tid, 0) + 1
                    if await self._async_stop_owned_find(tid, location_data):
                        self._cleanup_pending.discard(tid)
            if self.locate_started is None:
                return
            timed_out = force_timeout or time.monotonic() >= self._locate_deadline
            for tid in list(self._locate_pending):
                fix = fix_time((location_data or {}).get(tid))
                baseline = self._locate_baseline.get(tid)
                fresh = (
                    fix is not None
                    and (baseline is None or fix > baseline)
                    and fix >= self.locate_started - LOCATE_CLOCK_SLACK_SECONDS
                )
                if not fresh and not timed_out:
                    continue
                if not fresh:
                    self._locate_errors.append(
                        "No new position from " + self.tracker_name(tid)
                    )
                owned = self._locate_pending[tid]
                if owned and not await self._async_stop_owned_find(tid, location_data):
                    self._cleanup_pending.add(tid)
                    self._cleanup_attempts[tid] = 1
                    self._locate_errors.append(
                        "Find may still be active for " + self.tracker_name(tid)
                    )
                self._locate_pending.pop(tid)
            if not self._locate_pending:
                self._finish_locate()

    async def _async_stop_owned_find(self, tid, location_data):
        try:
            stopped = await self.client.async_stop_find_mode(tid)
        except Exception:
            stopped = False
        if not stopped:
            return False
        for data in (location_data, self.data):
            if data and tid in data:
                data[tid]["find_timer"] = 0
        return True

    def _finish_locate(self):
        if self._locate_cancel:
            self._locate_cancel()
            self._locate_cancel = None
        if self._locate_errors and all(
            s.startswith("No new position from ") for s in self._locate_errors
        ):
            self.locate_last_result = "No new position from " + ", ".join(
                s.removeprefix("No new position from ") for s in self._locate_errors
            )
        else:
            self.locate_last_result = (
                "; ".join(self._locate_errors) if self._locate_errors else "All found"
            )
        self.locate_started = None
        self.locate_last_finished = dt_util.utcnow()

    async def async_shutdown(self):
        if self._locate_cancel:
            self._locate_cancel()
            self._locate_cancel = None
        if self._locate_timeout_task and not self._locate_timeout_task.done():
            self._locate_timeout_task.cancel()
            await asyncio.gather(self._locate_timeout_task, return_exceptions=True)
        async with self._command_lock:
            owned = {
                t for t, own in self._locate_pending.items() if own
            } | self._cleanup_pending
            for tid in owned:
                if not await self._async_stop_owned_find(tid, self.data):
                    self.logger.warning(
                        "Pawfit Find cleanup could not be confirmed during unload"
                    )
            self._locate_pending.clear()
            self._cleanup_pending.clear()
            self.locate_started = None
        await super().async_shutdown()

    def _keep_last_data(self, err, now):
        """Ride out a failed fetch with the last known data (fork change).

        Pawfit's API sometimes stops answering for a few minutes. Upstream
        marked every entity unavailable on the first failure, so the cats
        vanished from maps. Here the last good data is kept, and the
        entities stay available, until KEEP_LAST_DATA_SECONDS after the last
        good fetch. The Last Time Seen sensor still shows how old it is.
        """
        if self._failing_since is None:
            self._failing_since = now
            self.logger.warning(
                "Pawfit fetch failed (%r); keeping the last known data for up to %d min",
                type(err).__name__,
                KEEP_LAST_DATA_SECONDS // 60,
            )
        if (
            self.data is not None
            and self._last_success is not None
            and now - self._last_success < KEEP_LAST_DATA_SECONDS
        ):
            return {
                tid: {**data, "data_cached": True} for tid, data in self.data.items()
            }
        raise UpdateFailed("No recent data from Pawfit") from None

    def _count_fetch(self) -> None:
        today = dt_util.now().date()
        if today != self._fetch_day:
            self._fetch_day = today
            self.fetches_today = 0
        self.fetches_today += 1

    async def _async_update_data(self):
        since = self._seconds_since_fetch()
        if since is not None and since < MIN_FETCH_SPACING_SECONDS:
            # Second guard: nothing reaches the Pawfit API inside the limit.
            self.logger.debug("Fetch skipped: last Pawfit fetch %.0f s ago", since)
            if self.data is not None and self.last_update_success:
                return self.data
            raise UpdateFailed("Waiting for the Pawfit rate limit")
        now = time.monotonic()
        self._last_fetch = now
        self._count_fetch()

        self.logger.debug(f"_async_update_data called for trackers: {self.tracker_ids}")
        try:
            location_data = await self.client.async_get_locations(self.tracker_ids)
        except PawfitAuthenticationError:
            raise ConfigEntryAuthFailed("Pawfit credentials were rejected") from None
        except Exception as err:  # timeouts, connection errors, bad responses
            await self._async_check_locate(None)
            return self._keep_last_data(err, time.monotonic())
        location_data = {str(k): v for k, v in (location_data or {}).items()}
        if not location_data:
            await self._async_check_locate(None)
            return self._keep_last_data(
                UpdateFailed("no trackers in Pawfit's response"), now
            )
        if self._failing_since is not None:
            self.logger.warning(
                "Pawfit fetch recovered after %.0f s", now - self._failing_since
            )
        self._failing_since = None
        self._last_success = time.monotonic()
        for tid, data in location_data.items():
            self._tracker_success[tid] = self._last_success
            data["data_cached"] = False
        # A partial account response must not erase another tracker's recent
        # position, nor keep it alive forever because a different pet responds.
        for tid, data in (self.data or {}).items():
            if (
                tid not in location_data
                and self._last_success - self._tracker_success.get(tid, -math.inf)
                < KEEP_LAST_DATA_SECONDS
            ):
                location_data[tid] = {**data, "data_cached": True}

        # The Find/Light/Alarm timers are in the same response; upstream
        # fetched it a second time to read them.
        for tracker_data in location_data.values():
            if tracker_data.get("data_cached"):
                continue
            raw = tracker_data.get("_raw") or {}
            tracker_data["find_timer"] = raw.get("timerGps", 0)
            tracker_data["light_timer"] = raw.get("timerLight", 0)
            tracker_data["alarm_timer"] = raw.get("timerSpeaker", 0)

        await self._async_update_activity(now)
        for tracker_id_str, tracker_data in location_data.items():
            stats = self._activity.get(tracker_id_str)
            if stats is not None:
                tracker_data.update(
                    {
                        "steps_today": stats.get("total_steps", 0),
                        "calories_today": stats.get("total_calories", 0.0),
                        "active_time_today": stats.get("total_active_hours", 0.0),
                    }
                )

        await self._async_check_locate(location_data)
        return location_data

    async def _async_update_activity(self, now) -> None:
        """Fetch daily activity if it is due (every 15 min, or a new day)."""
        # Same clock as the activity request's midnight-to-midnight window.
        today = self.client._now().date()
        due = (
            self._activity_fetched is None
            or today != self._activity_day
            # 30 s slack so a fetch landing a moment early still counts.
            or now - self._activity_fetched >= ACTIVITY_INTERVAL_SECONDS - 30
        )
        if not due:
            return
        self._activity_fetched = now
        if self._activity_day != today:
            self._activity.clear()
        self._activity_day = today
        for tracker_id in self.tracker_ids:
            # Keep the last valid same-day total if this optional request fails.
            try:
                stats = await self.client.async_get_activity_stats(str(tracker_id))
            except PawfitAuthenticationError:
                raise ConfigEntryAuthFailed(
                    "Pawfit credentials were rejected"
                ) from None
            except Exception:
                self.logger.debug("Optional Pawfit activity refresh failed")
                continue
            self.logger.debug(
                f"Received activity stats for tracker {tracker_id}: {stats}"
            )
            self._activity[str(tracker_id)] = stats


class PawfitDeviceTracker(TrackerEntity):
    _attr_should_poll = False

    def __init__(self, tracker, coordinator):
        self._tracker = tracker
        self._coordinator = coordinator
        self._tracker_id = tracker["tracker_id"]
        self._attr_name = f"{tracker['name']}'s PawFit Tracker"
        self._attr_unique_id = str(tracker["petId"])
        self._attr_source_type = SourceType.GPS
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(self._tracker_id))},
            "name": f"{tracker['name']}'s PawFit Tracker",
            "model": tracker.get("model", "Unknown"),
            "manufacturer": "PawFit",
            "translation_key": "pawfit_tracker",
        }
        self._attr_latitude = None
        self._attr_longitude = None
        self._attr_location_accuracy = None
        self._attr_charging = None

    @property
    def charging(self):
        return self._attr_charging

    @property
    def source_type(self):
        return self._attr_source_type

    @property
    def available(self):
        """Return if entity is available."""
        return (
            self._coordinator.last_update_success
            and self._attr_latitude is not None
            and self._attr_longitude is not None
        )

    def _fix_time(self):
        data = (
            self._coordinator.data.get(str(self._tracker_id), {})
            if self._coordinator.data
            else {}
        )
        return fix_time(data)

    def _is_stale(self) -> bool:
        fix = self._fix_time()
        return fix is None or time.time() - fix > STALE_AFTER_SECONDS

    @property
    def icon(self):
        """Fork change: a different icon while the position is stale."""
        return "mdi:map-marker-question" if self._is_stale() else "mdi:paw"

    @property
    def extra_state_attributes(self):
        """Fork change: when the tracker last reported its position."""
        fix = self._fix_time()
        data_cached = (
            (self._coordinator.data or {})
            .get(str(self._tracker_id), {})
            .get("data_cached", False)
        )
        if fix is None:
            return {
                "last_seen": None,
                "position_age_minutes": None,
                "stale": True,
                "data_cached": data_cached,
            }
        return {
            "data_cached": data_cached,
            "last_seen": dt_util.utc_from_timestamp(fix).isoformat(),
            "position_age_minutes": max(0, int((time.time() - fix) // 60)),
            "stale": time.time() - fix > STALE_AFTER_SECONDS,
        }

    def _update_attrs(self):
        data = (
            self._coordinator.data.get(str(self._tracker_id), {})
            if self._coordinator.data
            else {}
        )
        self._attr_latitude = coordinate(data.get("latitude"), -90, 90)
        self._attr_longitude = coordinate(data.get("longitude"), -180, 180)
        self._attr_location_accuracy = coordinate(data.get("accuracy"), 0, 10000000)

        # Handle charging status. Battery percentage is exposed by the dedicated
        # battery sensor because device tracker battery_level is deprecated.
        self._attr_charging = charging(
            data.get("battery"), data.get("_raw", {}).get("model")
        )

    async def async_update(self):
        await self._coordinator.async_request_refresh()
        self._update_attrs()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_attrs()
        # Register for coordinator updates
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Pawfit device tracker entities from a config entry."""
    # Get the coordinator from hass.data (created in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for tracker in coordinator.trackers:
        entities.append(PawfitDeviceTracker(tracker, coordinator))

    async_add_entities(entities)
