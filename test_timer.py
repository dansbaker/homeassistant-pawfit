#!/usr/bin/env python3
"""Test timer calculation logic"""

import time

# Values from your logs
timer_light_ms = 1750778656504
current_time_from_logs = 1750778656  # Approximate from log timestamp

print(f"Timer light (ms): {timer_light_ms}")
print(f"Timer light (seconds): {timer_light_ms / 1000.0}")
print(f"Current time (approx): {current_time_from_logs}")
print(f"Current time (actual): {time.time()}")

# Calculate elapsed time from the logs
timer_start_seconds = timer_light_ms / 1000.0
elapsed_seconds = current_time_from_logs - timer_start_seconds
print(f"Elapsed seconds at log time: {elapsed_seconds}")
print(f"Should be active (< 600s): {elapsed_seconds < 600}")

# Calculate remaining time
remaining_seconds = 600 - elapsed_seconds
print(f"Remaining seconds at log time: {remaining_seconds}")

print("\n--- Current calculation ---")
current_time_actual = time.time()
elapsed_now = current_time_actual - timer_start_seconds
remaining_now = 600 - elapsed_now
print(f"Elapsed seconds now: {elapsed_now}")
print(f"Remaining seconds now: {remaining_now}")
print(f"Should be active now: {elapsed_now < 600 and elapsed_now >= 0}")
