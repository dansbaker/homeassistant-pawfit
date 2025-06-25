import base64, zlib, json, pprint, aiohttp, asyncio

async def main():
    # You'll need to provide actual credentials here
    username = input("Enter Pawfit username: ")
    password = input("Enter Pawfit password: ")
    
    #Create a new aiohttp session
    session = aiohttp.ClientSession()
    headers = {"User-Agent":  "Pawfit/3 CFNetwork/1390 Darwin/22.0.0"}
    base_url = "https://pawfitapi.latsen.com/api/v1/"
    
    try:
        # First, try to login
        print("Attempting login...")
        login_url = base_url + "login/1/1"
        params = {"user": username, "pwd": password}
        
        async with session.get(login_url, params=params, headers=headers) as resp:
            print(f"Login Status: {resp.status}")
            resp_text = await resp.text()
            print(f"Login Response: {resp_text}")
            
            if resp.status == 200:
                try:
                    data = json.loads(resp_text)
                    user_id = data.get("data", {}).get("userId")
                    session_id = data.get("data", {}).get("sessionId")
                    
                    if user_id and session_id:
                        print(f"Login successful! UserID: {user_id}, SessionID: {session_id}")
                        
                        # Now try to get trackers with authentication
                        print("\nFetching trackers...")
                        trackers_url = base_url + f"trackers/{user_id}/{session_id}"
                        
                        async with session.get(trackers_url, headers=headers) as tracker_resp:
                            print(f"Trackers Status: {tracker_resp.status}")
                            tracker_text = await tracker_resp.text()
                            print(f"Trackers Response: {tracker_text}")
                            
                            if tracker_resp.status == 200 and tracker_text.strip():
                                tracker_data = json.loads(tracker_text)
                                print("\nParsed Trackers JSON:")
                                pprint.pprint(tracker_data)
                    else:
                        print("Login failed: No userId or sessionId in response")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse login JSON: {e}")
            else:
                print("Login failed with status code:", resp.status)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the session
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())

#s = "eJyrViouTU5OLS5WsiopKk3VUUpJLElUsqpWKskvScxRsjLQUcoFyiampwJVRMfW1gIAqpAQ-A=="
#decoded = zlib.decompress(base64.urlsafe_b64decode(s + '=='))
#pprint.pprint(json.loads(decoded))
