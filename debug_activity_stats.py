#!/usr/bin/env python3
"""Debug script to test activity stats API directly."""

import asyncio
import aiohttp
import logging
import sys
import os

# Add the custom_components path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'custom_components', 'pawfit'))

from pawfit_api import PawfitApiClient

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_activity_stats():
    """Test the activity stats API call."""
    # You'll need to replace these with your actual credentials
    username = input("Enter Pawfit username: ")
    password = input("Enter Pawfit password: ")
    
    async with aiohttp.ClientSession() as session:
        client = PawfitApiClient(username, password, session)
        
        try:
            # Login first
            print("Logging in...")
            login_result = await client.async_login()
            print(f"Login successful: {login_result}")
            
            # Get trackers
            print("\nFetching trackers...")
            trackers = await client.async_get_trackers()
            print(f"Found {len(trackers)} trackers: {[t.get('name', 'Unknown') for t in trackers]}")
            
            # Test activity stats for each tracker
            for tracker in trackers:
                tracker_id = tracker.get('tracker_id')
                tracker_name = tracker.get('name', 'Unknown')
                
                print(f"\n=== Testing activity stats for {tracker_name} (ID: {tracker_id}) ===")
                activity_stats = await client.async_get_activity_stats(str(tracker_id))
                print(f"Activity stats result: {activity_stats}")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_activity_stats())
