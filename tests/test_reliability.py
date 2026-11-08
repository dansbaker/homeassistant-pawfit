"""Regression tests for review findings; no real Pawfit calls or tracker commands."""

import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs

import pytest

from custom_components.pawfit.const import DOMAIN
from custom_components.pawfit.device_tracker import coordinate, fix_time
from custom_components.pawfit.helpers import battery_level, charging
from custom_components.pawfit.pawfit_api import calculate_api_sign
from .conftest import advance
from .test_rate_limit import entity_id, locate_entities, press


async def test_location_reauth_rebuilds_url_and_signature(
    hass, freezer, pawfit, setup_entry, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.pawfit.pawfit_api")
    pawfit.require_current_token = True
    pawfit.fail_next_location_with_403 = True
    await advance(hass, freezer, 61)
    urls = [url for endpoint, url in pawfit.urls if endpoint == "getlocationcaches"]
    assert urlsplit(urls[-2]).path.endswith("/u1/s1")
    assert urlsplit(urls[-1]).path.endswith("/u1/s2")
    assert parse_qs(urlsplit(urls[-1]).query)["sign"] == [
        calculate_api_sign("u1", "s2")
    ]
    api_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name.endswith("pawfit_api")
    )
    assert (
        "sessionId" not in api_logs
        and "spare@example.com" not in api_logs
        and "/u1/s" not in api_logs
    )


async def test_activity_failure_keeps_same_day_totals(
    hass, freezer, pawfit, setup_entry
):
    counter = entity_id(hass, "sensor", "11_steps_today")
    assert hass.states.get(counter).state == "120"
    pawfit.fail_activity = True
    await advance(hass, freezer, 901, step=5)
    assert hass.states.get(counter).state == "120"
    assert (
        hass.states.get(entity_id(hass, "device_tracker", "11")).state != "unavailable"
    )


async def test_locate_requires_a_new_fix_even_with_clock_slack(
    hass, freezer, pawfit, setup_entry
):
    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    # A five-second-old cached fix is inside clock slack, but isn't a NEW fix.
    for tid in pawfit.fix_times:
        pawfit.fix_times[tid] = datetime.now(timezone.utc).timestamp() - 5
    coordinator._last_fetch = None
    await coordinator.async_refresh()
    pawfit.reports_when_finding = False
    button, locating = locate_entities(hass, setup_entry)
    await press(hass, button)
    await advance(hass, freezer, 61)
    assert hass.states.get(locating).state == "on"
    assert pawfit.count("stoptracking") == 0


async def test_locate_start_failure_is_not_reported_as_found(
    hass, freezer, pawfit, setup_entry
):
    pawfit.fail_start.add("1001")
    button, locating = locate_entities(hass, setup_entry)
    await press(hass, button)
    await advance(hass, freezer, 61)
    assert (
        "Could not start Find for Tom"
        in hass.states.get(locating).attributes["last_result"]
    )
    assert "All found" != hass.states.get(locating).attributes["last_result"]


async def test_locate_stop_failure_is_visible_and_retried(
    hass, freezer, pawfit, setup_entry
):
    pawfit.fail_stop.add("1001")
    button, locating = locate_entities(hass, setup_entry)
    await press(hass, button)
    await advance(hass, freezer, 61)
    assert pawfit.finding["1001"]
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "11_find_mode_active")).state
        == "on"
    )
    assert hass.states.get(locating).attributes["cleanup_pending"] == ["Tom"]
    assert (
        "Find may still be active"
        in hass.states.get(locating).attributes["last_result"]
    )
    pawfit.fail_stop.clear()
    await advance(hass, freezer, 61)
    assert not pawfit.finding["1001"]
    assert hass.states.get(locating).attributes["cleanup_pending"] == []


async def test_locate_timeout_is_independent_of_polling(
    hass, freezer, pawfit, setup_entry
):
    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    button, locating = locate_entities(hass, setup_entry)
    pawfit.reports_when_finding = False
    await press(hass, button)
    coordinator._unsub_refresh()
    coordinator._unsub_refresh = None
    before = pawfit.count("getlocationcaches")
    await advance(hass, freezer, 181)
    assert pawfit.count("getlocationcaches") == before
    assert hass.states.get(locating).state == "off"
    assert not any(pawfit.finding.values())


async def test_unload_stops_only_locate_owned_find_modes(
    hass, freezer, pawfit, setup_entry
):
    await press(hass, entity_id(hass, "button", "11_find_mode_button"))
    await press(hass, locate_entities(hass, setup_entry)[0])
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    assert pawfit.finding["1001"] and not pawfit.finding["1002"]
    before = len(pawfit.calls)
    await advance(hass, freezer, 240, step=5)
    assert len(pawfit.calls) == before


async def test_manual_find_control_takes_ownership_during_locate(
    hass, freezer, pawfit, setup_entry
):
    await press(hass, locate_entities(hass, setup_entry)[0])
    await press(hass, entity_id(hass, "button", "11_find_mode_button"))
    assert not pawfit.finding["1001"]
    await advance(hass, freezer, 61)
    assert (
        pawfit.count("stoptracking") == 2
    )  # manual stop and other tracker's cleanup only


async def test_partial_response_preserves_missing_tracker_then_expires_it(
    hass, freezer, pawfit, setup_entry
):
    pawfit.omit_trackers.add("1002")
    tracker = entity_id(hass, "device_tracker", "12")
    battery = entity_id(hass, "sensor", "12_battery")
    await advance(hass, freezer, 5 * 60, step=5)
    assert hass.states.get(tracker).state != "unavailable"
    assert hass.states.get(tracker).attributes["data_cached"] is True
    await advance(hass, freezer, 11 * 60, step=5)
    assert hass.states.get(tracker).state == "unavailable"
    assert hass.states.get(battery).state == "unavailable"
    assert (
        hass.states.get(entity_id(hass, "device_tracker", "11")).state != "unavailable"
    )
    pawfit.omit_trackers.clear()
    await advance(hass, freezer, 61)
    assert hass.states.get(tracker).state != "unavailable"


async def test_zero_coordinates_are_valid(hass, freezer, pawfit, setup_entry):
    pawfit.coordinates["1001"] = {"latitude": 0, "longitude": 0}
    await advance(hass, freezer, 61)
    tracker = hass.states.get(entity_id(hass, "device_tracker", "11"))
    assert tracker.state != "unavailable"
    assert tracker.attributes["latitude"] == 0
    assert tracker.attributes["longitude"] == 0


@pytest.mark.parametrize(
    "value", [None, "bad", float("nan"), float("inf"), -1, 10**1000]
)
def test_invalid_position_timestamps_are_safe(value):
    assert fix_time({"_raw": {"state": {"location": {"utcDateTime": value}}}}) is None


@pytest.mark.parametrize("value", [None, "bad", True, float("nan"), float("inf"), 181])
def test_invalid_coordinates_do_not_break_updates(value):
    assert coordinate(value, -180, 180) is None


@pytest.mark.parametrize(
    "raw,model,level,on",
    [
        (3, "TR2A", 100, False),
        (5, "TR2A", None, True),
        (4, "TR2A", None, False),
        (-80, "TR3", 80, True),
        (80, "TR3", 80, False),
        ("bad", "TR3", None, None),
        (float("nan"), "TR3", None, None),
        (200, "TR3", None, None),
    ],
)
def test_battery_encodings_are_bounded(raw, model, level, on):
    assert battery_level(raw, model) == level
    assert charging(raw, model) == on


async def test_empty_account_response_obeys_outage_grace(
    hass, freezer, pawfit, setup_entry
):
    pawfit.omit_trackers.update(("1001", "1002"))
    await advance(hass, freezer, 61)
    tracker = entity_id(hass, "device_tracker", "11")
    assert hass.states.get(tracker).attributes["data_cached"] is True
    await advance(hass, freezer, 901, step=5)
    assert hass.states.get(tracker).state == "unavailable"
    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_auth_failure_does_not_hide_behind_cached_data(
    hass, freezer, pawfit, setup_entry
):
    pawfit.reject_locations = True
    pawfit.reject_login = True
    await advance(hass, freezer, 61)
    assert (
        hass.states.get(entity_id(hass, "device_tracker", "11")).state == "unavailable"
    )
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_command_connection_error_preserves_local_state(
    hass, pawfit, setup_entry
):
    from unittest.mock import patch
    from homeassistant.exceptions import HomeAssistantError

    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    with patch.object(
        coordinator.client,
        "async_start_light_mode",
        side_effect=TimeoutError("private"),
    ):
        with pytest.raises(HomeAssistantError, match="could not be delivered"):
            await press(hass, entity_id(hass, "button", "11_light_mode_button"))
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "11_light_mode_active")).state
        == "off"
    )


async def test_activity_midnight_failure_clears_previous_days_totals(
    hass, freezer, pawfit, setup_entry
):
    from datetime import timedelta

    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    coordinator._activity_day -= timedelta(days=1)
    pawfit.fail_activity = True
    await advance(hass, freezer, 61)
    assert (
        hass.states.get(entity_id(hass, "sensor", "11_steps_today")).state == "unknown"
    )


async def test_reload_preserves_entity_ids_and_removes_old_listeners(hass, setup_entry):
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    before = {
        entry.unique_id: entry.entity_id
        for entry in er.async_entries_for_config_entry(registry, setup_entry.entry_id)
    }
    old = hass.data[DOMAIN][setup_entry.entry_id]
    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert not old._listeners
    assert old._unsub_refresh is None
    after = {
        entry.unique_id: entry.entity_id
        for entry in er.async_entries_for_config_entry(registry, setup_entry.entry_id)
    }
    assert after == before
