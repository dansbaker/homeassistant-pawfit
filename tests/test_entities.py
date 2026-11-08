"""Invalid hardware payloads must not break entities or expose invalid values."""

import time

import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.pawfit.const import DOMAIN
from custom_components.pawfit.helpers import battery_code, mode_remaining
from custom_components.pawfit.device_tracker import PawfitDeviceTracker, fix_time
from custom_components.pawfit.sensor import (
    PawfitSensor,
    PawfitTimerSensor,
    PawfitTimestampSensor,
)
from custom_components.pawfit.binary_sensor import PawfitChargingSensor
from .conftest import advance
from .test_rate_limit import entity_id, press, locate_entities


@pytest.mark.parametrize(
    "value", [None, True, "bad", float("inf"), time.time() * 1000 + 10**9]
)
def test_invalid_mode_timer_is_off(value):
    assert mode_remaining(value) == 0


@pytest.mark.parametrize("value", [True, 1.5, "bad", float("inf")])
def test_invalid_battery_code_is_unknown(value):
    assert battery_code(value) is None


@pytest.mark.parametrize("data", [{}, {"_raw": {}}, {"_raw": {"state": {}}}])
def test_missing_fix_shapes_are_unknown(data):
    assert fix_time(data) is None


async def test_missing_entity_data_is_safe(hass, setup_entry):
    coordinator = hass.data[DOMAIN][setup_entry.entry_id]
    tracker = coordinator.trackers[0]
    entities = [
        PawfitSensor(tracker, coordinator, "battery", "Battery"),
        PawfitTimestampSensor(tracker, coordinator, "last_update", "Last seen"),
        PawfitTimerSensor(tracker, coordinator, "find_timer", "Timer"),
        PawfitChargingSensor(tracker, coordinator),
    ]
    coordinator.data = None
    assert all(not entity.available for entity in entities)
    assert entities[0].native_value is None
    assert entities[1].native_value is None
    assert entities[2].native_value == 0
    assert entities[2].extra_state_attributes == {}
    assert entities[3].is_on is None
    device = PawfitDeviceTracker(tracker, coordinator)
    device._update_attrs()
    assert device.extra_state_attributes["last_seen"] is None
    assert device.icon == "mdi:map-marker-question"
    assert device.charging is None


@pytest.mark.parametrize("mode", ["find", "light", "alarm"])
async def test_controls_toggle_and_rejected_command_does_not_change_state(
    hass, pawfit, setup_entry, mode
):
    button = entity_id(hass, "button", f"11_{mode}_mode_button")
    sensor = entity_id(hass, "binary_sensor", f"11_{mode}_mode_active")
    await press(hass, button)
    assert hass.states.get(sensor).state == "on"
    pawfit.fail_stop.add("1001")
    with pytest.raises(HomeAssistantError, match="rejected"):
        await press(hass, button)
    assert hass.states.get(sensor).state == "on"
    pawfit.fail_stop.clear()
    await press(hass, button)
    assert hass.states.get(sensor).state == "off"


async def test_locate_all_start_failures_and_repeated_press(hass, pawfit, setup_entry):
    button, locating = locate_entities(hass, setup_entry)
    pawfit.fail_start.update(("1001", "1002"))
    with pytest.raises(HomeAssistantError, match="could not start"):
        await press(hass, button)
    assert hass.states.get(locating).state == "off"
    assert "Could not start Find" in hass.states.get(locating).attributes["last_result"]
    pawfit.fail_start.clear()
    await press(hass, button)
    count = pawfit.count("starttracking")
    await press(hass, button)
    assert pawfit.count("starttracking") == count


async def test_cleanup_attempts_are_bounded_and_new_locate_is_blocked(
    hass, freezer, pawfit, setup_entry
):
    pawfit.fail_stop.add("1001")
    button, locating = locate_entities(hass, setup_entry)
    await press(hass, button)
    await advance(hass, freezer, 300, step=5)
    # Tom's three attempts plus Ginger's successful stop.
    assert pawfit.count("stoptracking") == 4
    assert hass.states.get(locating).attributes["cleanup_pending"] == ["Tom"]
    with pytest.raises(HomeAssistantError, match="cleanup is pending"):
        await press(hass, button)
