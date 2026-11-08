"""Validate the tracker encodings before exposing them to HA."""

import math
import time


def battery_code(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


def battery_level(value, model):
    value = battery_code(value)
    if value is None:
        return None
    if model == "TR2A":
        return round(value / 3 * 100) if 0 <= value <= 3 else None
    return abs(value) if -100 <= value <= 100 else None


def charging(value, model):
    value = battery_code(value)
    if (
        value is None
        or (model == "TR2A" and value < 0)
        or (model != "TR2A" and abs(value) > 100)
    ):
        return None
    return value > 4 if model == "TR2A" else value < 0


def mode_remaining(timer_ms):
    """Remaining seconds in a valid ten-minute mode; malformed/future clocks are off."""
    if isinstance(timer_ms, bool):
        return 0
    try:
        elapsed = time.time() - float(timer_ms) / 1000
        return 600 - elapsed if math.isfinite(elapsed) and 0 <= elapsed < 600 else 0
    except (TypeError, ValueError, OverflowError):
        return 0
