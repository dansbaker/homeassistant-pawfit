import base64, zlib, json, pprint, aiohttp, asyncio
from datetime import datetime, timezone
import time

def compile_daily_stats(activity_data):
    """Compile hourly stats into daily summaries."""
    activities = activity_data.get('data', {}).get('activities', [])
    daily_summaries = []
    
    for day_activity in activities:
        day_pos = day_activity.get('dayPos', 0)
        day_timestamp = day_activity.get('timestamp', 0)
        hourly_stats = day_activity.get('hourlyStats', [])
        
        # Initialize daily totals
        daily_totals = {
            'day_pos': day_pos,
            'date': datetime.fromtimestamp(day_timestamp / 1000).strftime('%Y-%m-%d'),
            'timestamp': day_timestamp,
            'total_calories': 0.0,
            'total_distance': 0.0,
            'total_active_hours': 0.0,
            'total_rest_hours': 0.0,
            'total_steps': 0,  # Add steps calculation
            'avg_pace': 0,
            'max_pace': 0,
            'active_periods': 0,
            'hourly_breakdown': []
        }
        
        active_paces = []
        
        for hour_stat in hourly_stats:
            # Sum up the totals
            daily_totals['total_calories'] += hour_stat.get('calorie', 0.0)
            daily_totals['total_distance'] += hour_stat.get('distance', 0.0)
            daily_totals['total_active_hours'] += hour_stat.get('active', 0.0)
            daily_totals['total_rest_hours'] += hour_stat.get('rest', 0.0)
            
            pace = hour_stat.get('pace', 0)
            daily_totals['total_steps'] += pace  # Steps = sum of all pace values
            
            if pace > 0:
                active_paces.append(pace)
                daily_totals['active_periods'] += 1
            
            if pace > daily_totals['max_pace']:
                daily_totals['max_pace'] = pace
            
            # Add hour breakdown for reference
            hour_time = datetime.fromtimestamp(hour_stat.get('timestamp', 0) / 1000)
            daily_totals['hourly_breakdown'].append({
                'hour': hour_time.strftime('%H:%M'),
                'active': hour_stat.get('active', 0.0),
                'calories': hour_stat.get('calorie', 0.0),
                'distance': hour_stat.get('distance', 0.0),
                'pace': pace,
                'steps': pace  # pace = steps for that hour
            })
        
        # Calculate averages
        if active_paces:
            daily_totals['avg_pace'] = sum(active_paces) / len(active_paces)
        
        # Calculate total pace (distance per active hour)
        if daily_totals['total_active_hours'] > 0:
            daily_totals['total_pace'] = daily_totals['total_distance'] / daily_totals['total_active_hours']
        else:
            daily_totals['total_pace'] = 0
        
        # Convert distance from meters to more readable units
        daily_totals['total_distance_km'] = daily_totals['total_distance'] / 1000
        daily_totals['total_distance_miles'] = daily_totals['total_distance'] / 1609.34
        
        daily_summaries.append(daily_totals)
    
    return daily_summaries

async def main():
    #Create a new aiohttp session
    session = aiohttp.ClientSession()
    headers = {"User-Agent":  "Pawfit/3 CFNetwork/1390 Darwin/22.0.0"}
    
    # Calculate today's date range (midnight to midnight)
    now = datetime.now()
    # Get midnight of today (start of today)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Get midnight of tomorrow (end of today)
    tomorrow_midnight = today_midnight.replace(hour=23, minute=59, second=59, microsecond=999000)
    
    # Convert to millisecond timestamps
    start_timestamp = int(today_midnight.timestamp() * 1000)
    end_timestamp = int(tomorrow_midnight.timestamp() * 1000)
    
    print(f"Fetching data for: {today_midnight.strftime('%Y-%m-%d %H:%M:%S')} to {tomorrow_midnight.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timestamps: start={start_timestamp}, end={end_timestamp}")
    
    # Note: You'll need to replace the user_id, session_id, and tracker_id with actual values
    url = f"https://pawfitapi.latsen.com/api/v1/getactivitystatzip/1/1/814841991/908963310855879410?end={end_timestamp}&start={start_timestamp}&tracker=1551224760"
    try:
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            print(f"Headers: {dict(resp.headers)}")
            resp_text = await resp.text()
            decoded = zlib.decompress(base64.urlsafe_b64decode(resp_text + '=='))
            raw_data = json.loads(decoded)
            
            print("=== DAILY ACTIVITY SUMMARY ===")
            daily_stats = compile_daily_stats(raw_data)
            for day in daily_stats:
                print(f"\nDate: {day['date']}")
                print(f"Total Steps: {day['total_steps']}")
                print(f"Total Calories: {day['total_calories']:.2f}")
                print(f"Total Active Time: {day['total_active_hours']:.2f} hours")
          
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the session
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())

#s = "eJyrViouTU5OLS5WsiopKk3VUUpJLElUsqpWKskvScxRsjLQUcoFyiampwJVRMfW1gIAqpAQ-A=="
#
#pprint.pprint(json.loads(decoded))