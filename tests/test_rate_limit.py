"""The fork's rate limit: one location fetch a minute, whatever happens."""

from datetime import datetime, timezone

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import DOMAIN, MockConfigEntry, advance


def entity_id(hass, platform, unique_id):
    eid = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert eid, f"{platform} {unique_id} not registered"
    return eid


def gaps(times):
    return [b - a for a, b in zip(times, times[1:])]


async def test_setup_requests(hass, pawfit, setup_entry):
    """Setup: one login, the tracker list, one location fetch, activity per cat."""
    assert pawfit.since(0) == [
        "login", "listpetinvitee", "getlocationcaches",
        "getactivitystatzip", "getactivitystatzip",
    ]
    counter = hass.states.get(entity_id(hass, "sensor", f"{setup_entry.entry_id}_api_requests_today"))
    assert counter.state == "5"
    assert counter.attributes["location_fetches_today"] == 1
    assert hass.states.get(entity_id(hass, "sensor", "11_steps_today")).state == "120"


async def test_steady_state(hass, freezer, pawfit, setup_entry):
    """31 minutes of normal running, every timer (entity polling too) firing."""
    await advance(hass, freezer, 31 * 60)

    loc = pawfit.times("getlocationcaches")
    print(f"\nlocation fetches in 31 min: {len(loc)}; gaps {min(gaps(loc)):.1f}-{max(gaps(loc)):.1f} s; "
          f"activity calls: {pawfit.count('getactivitystatzip')}; total requests: {len(pawfit.calls)}")
    assert len(loc) == 32  # t=0 plus one a minute
    assert min(gaps(loc)) >= 55
    assert max(gaps(loc)) <= 62
    assert pawfit.count("getactivitystatzip") == 6  # 2 cats at 0, 15 and 30 min
    assert pawfit.count("login") == 1
    assert pawfit.count("listpetinvitee") == 1

    counter = hass.states.get(entity_id(hass, "sensor", f"{setup_entry.entry_id}_api_requests_today"))
    assert int(counter.state) == len(pawfit.calls)
    assert counter.attributes["location_fetches_today"] == 32


async def test_update_entity_spam(hass, freezer, pawfit, setup_entry):
    """homeassistant.update_entity every 5 s can't make it fetch more often,
    and can't starve the schedule either."""
    assert await async_setup_component(hass, "homeassistant", {})
    tracker = entity_id(hass, "device_tracker", "11")

    async def spam():
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": tracker}, blocking=True
        )

    await advance(hass, freezer, 5 * 60, step=5, each=spam)

    loc = pawfit.times("getlocationcaches")
    print(f"\nwith update_entity every 5 s: {len(loc)} location fetches in 5 min; "
          f"gaps {min(gaps(loc)):.1f}-{max(gaps(loc)):.1f} s")
    assert len(loc) == 6
    assert min(gaps(loc)) >= 59
    assert max(gaps(loc)) <= 61


async def test_find_button(hass, freezer, pawfit, setup_entry):
    """A button press is one command request: no extra fetch, no 1 s polling."""
    button = entity_id(hass, "button", "11_find_mode_button")
    active = entity_id(hass, "binary_sensor", "11_find_mode_active")
    assert hass.states.get(active).state == "off"

    start = len(pawfit.calls)
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done()
    assert pawfit.since(start) == ["starttracking"]
    assert hass.states.get(active).state == "on"  # shown at once, from the local timer

    await advance(hass, freezer, 30)
    assert pawfit.since(start) == ["starttracking"]  # nothing else inside the minute

    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done()
    assert pawfit.since(start) == ["starttracking", "stoptracking"]
    assert hass.states.get(active).state == "off"

    await advance(hass, freezer, 40)
    assert pawfit.since(start) == ["starttracking", "stoptracking", "getlocationcaches"]
    assert hass.states.get(active).state == "off"  # Pawfit agrees


async def test_reauth_is_counted(hass, freezer, pawfit, setup_entry):
    """An expired session costs a login and one retry, and both are counted."""
    pawfit.fail_next_location_with_403 = True
    start = len(pawfit.calls)
    await advance(hass, freezer, 61)
    assert pawfit.since(start) == ["getlocationcaches", "login", "getlocationcaches"]
    counter = hass.states.get(entity_id(hass, "sensor", f"{setup_entry.entry_id}_api_requests_today"))
    assert int(counter.state) == len(pawfit.calls)


async def test_midnight(hass, freezer, pawfit):
    """The daily count resets at local midnight; activity is refetched on a new day."""
    # 23:58 in London is 22:58 UTC; the test process's local clock is UTC.
    freezer.move_to(datetime(2026, 10, 6, 22, 58, 0, tzinfo=timezone.utc))
    await hass.config.async_set_time_zone("Europe/London")
    entry = MockConfigEntry(domain=DOMAIN, title="Pawfit Account",
                            data={"username": "a", "password": "b", "userId": "u1", "sessionId": "s1"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    counter_id = entity_id(hass, "sensor", f"{entry.entry_id}_api_requests_today")

    await advance(hass, freezer, 180, step=5)  # past London midnight
    counter = hass.states.get(counter_id)
    assert counter.attributes["counting_since"].startswith("2026-10-07T00:00:00+01:00")
    assert int(counter.state) < len(pawfit.calls)  # only today's requests

    # Run past midnight UTC (the activity window's clock): activity is fetched
    # in the first refresh of the new day, not 15 minutes later.
    await advance(hass, freezer, 62 * 60, step=5)
    midnight_utc = datetime(2026, 10, 7, tzinfo=timezone.utc).timestamp()
    activity = pawfit.wall_times("getactivitystatzip")
    first_after = min(t for t in activity if t >= midnight_utc)
    assert first_after - midnight_utc <= 65
    loc = pawfit.times("getlocationcaches")
    assert min(gaps(loc)) >= 55


async def test_pawfit_stops_answering(hass, freezer, pawfit, setup_entry):
    """A few minutes of timeouts keep the last positions; 15 minutes of them don't."""
    tracker = entity_id(hass, "device_tracker", "11")
    before = hass.states.get(tracker).state
    assert before != "unavailable"

    pawfit.location_hangs = True
    await advance(hass, freezer, 5 * 60)
    assert hass.states.get(tracker).state == before  # still on the map

    pawfit.location_hangs = False
    await advance(hass, freezer, 61)
    assert hass.states.get(tracker).state == before

    # A long outage: after 15 min without a good fetch the trackers go unavailable.
    pawfit.location_hangs = True
    await advance(hass, freezer, 14 * 60)
    assert hass.states.get(tracker).state == before
    await advance(hass, freezer, 2 * 60)
    assert hass.states.get(tracker).state == "unavailable"

    # And they come back with the first good fetch.
    pawfit.location_hangs = False
    await advance(hass, freezer, 61)
    assert hass.states.get(tracker).state == before

    # Timed-out requests still count, and still no more than one a minute.
    loc = pawfit.times("getlocationcaches")
    assert min(gaps(loc)) >= 55


def locate_entities(hass, entry):
    return (
        entity_id(hass, "button", f"{entry.entry_id}_locate"),
        entity_id(hass, "binary_sensor", f"{entry.entry_id}_locating"),
    )


async def press(hass, button):
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done()


async def test_locate(hass, freezer, pawfit, setup_entry):
    """Locate: Find on for both, off again for each as soon as it reports."""
    button, locating = locate_entities(hass, setup_entry)
    tracker = entity_id(hass, "device_tracker", "11")
    assert hass.states.get(tracker).attributes["stale"] is True  # the fake's fix is old
    assert hass.states.get(tracker).attributes["icon"] == "mdi:map-marker-question"
    assert hass.states.get(locating).state == "off"

    start = len(pawfit.calls)
    await press(hass, button)
    assert pawfit.since(start) == ["starttracking", "starttracking"]
    assert hass.states.get(locating).state == "on"
    assert hass.states.get(locating).attributes["icon"] == "mdi:loading"
    assert hass.states.get(locating).attributes["waiting_for"] == ["Tom", "Ginger"]

    await press(hass, button)  # a second press while it's running does nothing
    assert pawfit.since(start) == ["starttracking", "starttracking"]

    await advance(hass, freezer, 61)  # the next scheduled fetch has fresh fixes
    calls = pawfit.since(start)
    assert calls.count("getlocationcaches") == 1
    assert calls.count("stoptracking") == 2
    assert not any(pawfit.finding.values())
    state = hass.states.get(locating)
    assert state.state == "off"
    assert state.attributes["last_result"] == "All found"
    attrs = hass.states.get(tracker).attributes
    assert attrs["stale"] is False
    assert attrs["position_age_minutes"] <= 1
    assert attrs["icon"] == "mdi:paw"


async def test_locate_times_out(hass, freezer, pawfit, setup_entry):
    """No fresh fix within 3 minutes: Find goes off again and it says who's missing."""
    button, locating = locate_entities(hass, setup_entry)
    pawfit.reports_when_finding = False
    start = len(pawfit.calls)
    await press(hass, button)
    await advance(hass, freezer, 150)
    assert hass.states.get(locating).state == "on"
    assert "stoptracking" not in pawfit.since(start)
    await advance(hass, freezer, 60)
    state = hass.states.get(locating)
    assert state.state == "off"
    assert state.attributes["last_result"] == "No new position from Tom, Ginger"
    assert pawfit.since(start).count("stoptracking") == 2
    assert min(gaps(pawfit.times("getlocationcaches"))) >= 55


async def test_locate_leaves_find_mode_alone(hass, freezer, pawfit, setup_entry):
    """A tracker already in Find mode isn't started or stopped by Locate."""
    button, locating = locate_entities(hass, setup_entry)
    await press(hass, entity_id(hass, "button", "11_find_mode_button"))  # Tom
    start = len(pawfit.calls)
    await press(hass, button)
    assert pawfit.since(start) == ["starttracking"]  # Ginger only
    await advance(hass, freezer, 61)
    assert pawfit.since(start).count("stoptracking") == 1
    assert pawfit.finding["1001"] is True  # Tom's Find mode still on
    assert hass.states.get(locating).state == "off"
