# Domain constant for the Pawfit integration
DOMAIN = "pawfit"

BASE_URL = "https://pawfitapi.latsen.com/api/v1/"
USER_AGENT = "Pawfit/3 CFNetwork/1390 Darwin/22.0.0"

# Rate limiting (fork change). Location is fetched on a fixed 60 s schedule,
# and requests for an extra refresh (homeassistant.update_entity etc.) are
# ignored until 60 s have passed. MIN_FETCH_SPACING is a second, hard floor
# on any two fetches, a little under 60 s only so that the scheduler's
# rounding (up to 1 s) never makes a scheduled fetch get skipped.
UPDATE_INTERVAL_SECONDS = 60
MIN_FETCH_SPACING_SECONDS = 55
# Daily activity (steps, calories, active time) changes slowly: fetch it at
# most every 15 minutes, and again straight after midnight.
ACTIVITY_INTERVAL_SECONDS = 15 * 60
# If Pawfit stops answering, keep showing the last known data (entities stay
# available) until this long after the last good fetch.
KEEP_LAST_DATA_SECONDS = 15 * 60
# Give up on a single Pawfit request after this long.
REQUEST_TIMEOUT_SECONDS = 30
# Locate: Find mode is turned on, then off again for each tracker as soon as
# it reports a position newer than the press; give up after this long.
LOCATE_TIMEOUT_SECONDS = 3 * 60
# A position up to this much older than the press still counts (clock skew).
LOCATE_CLOCK_SLACK_SECONDS = 10
# A tracker's position counts as stale (attribute on the device tracker) when
# it last reported more than this long ago.
STALE_AFTER_SECONDS = 15 * 60
