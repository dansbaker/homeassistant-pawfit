# Pawfit for Home Assistant

A community integration for Pawfit pet trackers: locations, battery and charging, signal, daily activity, and Find, Light and Alarm controls. This integration is unofficial and is not supported by Pawfit.

Thanks to **[@fullstackfool](https://github.com/fullstackfool/homeassistant-pawfit)** for contributing rate-limited polling, a shared HTTP session, request counting, an outage grace period, Locate and stale-position information through their fork. Their original commits are preserved in this repository. Community fixes and contributions are welcome.

## Use a separate Pawfit account

**Do not use your main Pawfit account.** Pawfit sessions can displace the mobile app's login. Create another account, share your pets with it, sign into that account in the Pawfit app to accept the invitations, then return the app to your main account. Use the separate account's credentials in Home Assistant.

## Install

Home Assistant **2026.9 or newer** is required. Automated tests currently cover 2026.9.4 and 2026.10.4; see [development](#development) for the exact environments.

In HACS, add `https://github.com/dansbaker/homeassistant-pawfit` as a custom **Integration** repository, download Pawfit and restart Home Assistant. Then add **Pawfit Pet Tracker** under **Settings → Devices & services → Add integration**.

For manual installation, copy `custom_components/pawfit` from this repository into your Home Assistant configuration's `custom_components` directory. Alternatively, extract the release's `pawfit.zip` **into `custom_components/pawfit/`**. Restart Home Assistant and add the integration.

If credentials expire, use Home Assistant's reauthentication prompt. Connection failures and unexpected API responses are reported separately from rejected credentials. Only one Pawfit account can be configured.

## Entities and controls

Each tracker provides:

- A GPS device tracker with accuracy, last-seen time, position age, `stale` and `data_cached` attributes.
- Battery percentage, charging status, signal strength and last-seen sensors.
- Daily steps, calories and active time (hours).
- Find, Light and Alarm toggle buttons, active-state binary sensors and remaining-time sensors.

Modes have a ten-minute timer reported by Pawfit. Press the corresponding button again to stop a mode early. Local state changes only after the API acknowledges the command; this acknowledges delivery to Pawfit, not physical operation of the tracker. Timers update with the polling cycle rather than every second.

The account also provides a **Locate** button, a **Locating** binary sensor and an API request counter. Entity IDs depend on Home Assistant's naming and existing registry; existing tracker and mode unique IDs are preserved on upgrade.

### Locate

Locate temporarily enables Find for each tracker and waits for a **new** position relative to its starting position. It stops the Find modes it started when a new fix arrives, or after three minutes. Trackers already in Find mode remain under your control. A manual Find press during Locate takes ownership of that tracker's mode.

Positions are still checked at most once a minute. A successful Locate means Pawfit returned a newer position; it does not independently verify GPS accuracy or the pet's physical location.

The Locating sensor exposes `waiting_for`, `last_result` and `cleanup_pending`. Failed starts and failed stop acknowledgements are reported. Failed stops receive at most three automatic attempts; if cleanup remains pending, inspect the Pawfit app or use the Find toggle to switch it off before starting Locate again. Unloading the integration attempts to stop only Find modes owned by Locate.

### Polling, outages and stale positions

- Location, battery, signal and mode timers use **one account request per minute**, with a hard minimum spacing of 55 seconds. Extra refresh requests do not bypass this limit.
- Activity uses **one request per tracker every 15 minutes**, and refreshes after midnight in Home Assistant's timezone.
- Button presses add command requests; activating a mode does not start rapid polling.
- During a transient outage, recent readings remain available for up to **15 minutes**, marked `data_cached: true`. Missing trackers in partial responses expire independently. Authentication failures request reauthentication immediately.
- Cached readings are last-known data. Inspect **Last Time Seen**, `position_age_minutes` and `stale`; an available map marker does not mean a tracker is online. Positions older than 15 minutes have a question-mark icon.
- Failed activity requests retain the last valid same-day totals rather than replacing them with zero. A new day's totals remain unknown until fetched successfully.

With two trackers, the scheduled requests total about **1,632 per day**, excluding login, retries and commands. The diagnostic counter includes every HTTP request, including retries and commands; its count starts at integration setup and resets at local midnight.

## Troubleshooting and contributions

Report problems in [GitHub issues](https://github.com/dansbaker/homeassistant-pawfit/issues). Include your Home Assistant version, integration version, tracker model, expected behaviour, last-seen time and whether data is marked stale/cached. For Locate, include `last_result` and `cleanup_pending`. Remove account details, tokens, tracker identifiers and precise coordinates from anything you share. Do not post passwords or raw authenticated API URLs.

The integration uses a reverse-engineered cloud API, which may change. Hardware behaviour still needs testing on different tracker models. Please use the Pawfit app for time-critical tracking.

See [0.5.0 release notes](docs/releases/0.5.0.md) and the [review record](docs/community-review.md) for the imported work, fixes and remaining limitations.

## Development

Use Python 3.14 and an isolated environment:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_test.txt
python -m pytest --cov=custom_components.pawfit --cov-branch --cov-report=term-missing --cov-fail-under=95
ruff check custom_components tests
ruff format --check custom_components tests
```

`requirements_test.txt` pins the HA 2026.9.4 test harness. `requirements_test_2026_10.txt` pins the HA 2026.10.4 harness; run it in a separate environment. CI runs both and enforces **95% combined statement/branch coverage**. Tests use synthetic API responses and fake time; they never log into a real account or command real trackers.

Coverage includes polling limits, outage/recovery, partial responses, reauthentication, malformed responses, command failures, Locate ownership and cleanup, setup/unload and registry stability. These tests do not prove physical tracker behaviour or compatibility with untested Home Assistant versions.

## License

Apache 2.0
