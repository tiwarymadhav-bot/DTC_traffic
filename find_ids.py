import asyncio
import aiohttp
import random

async def fetch_real_route(session, route_uid, csrf_token):
    spoofed_ip = f"203.0.113.{random.randint(1, 250)}"
    url = "https://www.dtcbusroutes.in/api/live/buses/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-CSRFToken": csrf_token,
        "Referer": "https://www.dtcbusroutes.in/",
        "Content-Type": "application/json",
        "X-Forwarded-For": spoofed_ip,
        "Client-IP": spoofed_ip
    }
    payload = {"route_id": str(route_uid)}
    try:
        async with session.post(url, headers=headers, json=payload, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return route_uid, data.get("buses", [])
    except:
        pass
    return route_uid, []

async def main():
    async with aiohttp.ClientSession() as session:
        await session.get("https://www.dtcbusroutes.in/")
        csrf_token = ""
        for cookie in session.cookie_jar:
            if cookie.key == "csrftoken":
                csrf_token = cookie.value
        
        found = {}
        for chunk in range(1, 4000, 100):
            print(f"Checking {chunk} to {chunk+99}...")
            tasks = [fetch_real_route(session, i, csrf_token) for i in range(chunk, chunk+100)]
            results = await asyncio.gather(*tasks)
            for uid, buses in results:
                if buses:
                    route_name = buses[0].get("route", "").upper()
                    if "433" in route_name or "473" in route_name or "429" in route_name:
                        print(f"FOUND: Route {route_name} = {uid}")
                        found[route_name] = uid
            if len(found) >= 6: # UP and DOWN for all 3
                break

asyncio.run(main())
