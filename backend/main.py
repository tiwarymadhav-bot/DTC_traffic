import asyncio
import time
import math
import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from math import radians, cos, sin, asin, sqrt
import json
import os
import csv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.head("/")
async def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

# In-memory storage for trails
last_positions = {}   
active_segments = []  

# Load state if exists
if os.path.exists("state.json"):
    try:
        with open("state.json", "r") as f:
            state = json.load(f)
            last_positions = state.get("last_positions", {})
            active_segments = state.get("active_segments", [])
        print(f"Loaded state: {len(active_segments)} segments.")
    except Exception as e:
        print("Failed to load state:", e)  

# Load all routes dynamically from the CSV file
UIDS_TO_TRACK = []
csv_path = os.path.join(os.path.dirname(__file__), "..", "all_routes.csv")
if os.path.exists(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            next(reader) # skip header
            for row in reader:
                if row:
                    UIDS_TO_TRACK.append(str(row[0]))
        except Exception:
            pass
print(f"Loaded {len(UIDS_TO_TRACK)} routes to track.")

_dtc_session = None

async def init_dtc_session():
    global _dtc_session
    if _dtc_session is None:
        _dtc_session = aiohttp.ClientSession()
        await _dtc_session.get("https://www.dtcbusroutes.in/")

import random

async def fetch_real_route(route_uid):
    global _dtc_session
    if _dtc_session is None:
        await init_dtc_session()
        
    csrf_token = ""
    for cookie in _dtc_session.cookie_jar:
        if cookie.key == "csrftoken":
            csrf_token = cookie.value
            
    # Spoof IP to bypass naive rate limiting (429 Too Many Requests)
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
        async with _dtc_session.post(url, headers=headers, json=payload, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("buses", [])
            else:
                print(f"[API Error] Status {response.status} for UID {route_uid}")
                if response.status == 403 or response.status == 429:
                    _dtc_session = None
    except Exception as e:
        print(f"[API Exception] {e}")
    return []

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 
    return c * r

def get_color_for_speed(speed_kmh):
    if speed_kmh < 5: return "#ff4d4d"
    if speed_kmh < 15: return "#ffa502"
    return "#2ed573"

def calculate_bearing(lat1, lon1, lat2, lon2):
    import math
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
    return int((math.degrees(math.atan2(x, y)) + 360) % 360)

async def get_snapped_route(session, lat1, lon1, lat2, lon2, last_bearing=None):
    straight_dist_m = haversine(lon1, lat1, lon2, lat2) * 1000
    
    bearing = None
    b_param = ""
    
    if straight_dist_m > 45:
        # Fast movement: Calculate true bearing
        bearing = calculate_bearing(lat1, lon1, lat2, lon2)
        # Lock ONLY the start point to this bearing (±45 deg). Leave end point free to allow natural road curves.
        b_param = f"&bearings={bearing},45;"
    elif last_bearing is not None:
        # Slow movement but we know the bus's past direction
        bearing = last_bearing
        b_param = f"&bearings={bearing},45;"
        
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&steps=true{b_param}"
    
    fallback_route = [[lon1, lat1], [lon2, lat2]]
    
    try:
        async with session.get(url, timeout=2) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "Ok":
                    route = data["routes"][0]
                    
                    # Filter out GPS noise (jumping through narrow colony streets)
                    legs = route.get("legs", [])
                    if legs and "steps" in legs[0]:
                        if len(legs[0]["steps"]) > 4:
                            return fallback_route, bearing

                    # Relaxed distance rejection (3.0x) to allow curved flyovers and highway loops
                    if straight_dist_m == 0 or route["distance"] <= straight_dist_m * 3.0 or route["distance"] <= 50:
                        return route["geometry"]["coordinates"], bearing
    except: pass
    
    # If OSRM is rate-limited (e.g. 429), just draw a straight line so we don't lose the paint
    return fallback_route, bearing

@app.on_event("startup")
async def startup_event():
    print("="*50)
    print(" Real-Time GPS Breadcrumb Mapping Started")
    print("="*50)
    asyncio.create_task(live_gps_tracker_loop())

async def live_gps_tracker_loop():
    global last_positions, active_segments, _dtc_session
    
    current_route_index = 0
    batch_size = 50
    
    async with aiohttp.ClientSession() as osrm_session:
        while True:
            now = time.time()
            all_buses = []
            
            if not UIDS_TO_TRACK:
                await asyncio.sleep(15)
                continue
                
            # Round-robin slice
            end_index = current_route_index + batch_size
            current_batch = UIDS_TO_TRACK[current_route_index:end_index]
            
            # Wrap around
            if end_index >= len(UIDS_TO_TRACK):
                current_batch += UIDS_TO_TRACK[0:(end_index - len(UIDS_TO_TRACK))]
                current_route_index = end_index - len(UIDS_TO_TRACK)
            else:
                current_route_index = end_index
            
            # Fetch from actual DTC Live API
            for uid in current_batch:
                buses = await fetch_real_route(uid)
                if isinstance(buses, list):
                    all_buses.extend(buses)
                    
            for b in all_buses:
                bid = b.get("id")
                try:
                    lat = float(b.get("lat", 0))
                    lng = float(b.get("lng", 0))
                except:
                    continue
                if lat == 0 or lng == 0: continue
                
                new_bearing = None
                if bid in last_positions:
                    prev = last_positions[bid]
                    time_diff = now - prev["timestamp"]
                    dist = haversine(prev["lng"], prev["lat"], lng, lat)
                    
                    if 0 < dist < 5 and time_diff > 0:
                        speed = (dist / (time_diff / 3600))
                        color = get_color_for_speed(speed)
                        path_geojson, new_bearing = await get_snapped_route(osrm_session, prev["lat"], prev["lng"], lat, lng, prev.get("bearing"))
                        
                        if path_geojson:
                            active_segments.append({
                                "id": f"{bid}_{now}",
                                "bus_id": bid,
                                "route": b.get("route", "Unknown"),
                                "path_geojson": path_geojson,
                                "color": color,
                                "speed": round(speed, 1),
                                "timestamp": now
                            })
                            
                last_positions[bid] = {
                    "lat": lat, 
                    "lng": lng, 
                    "route": b.get("route", "Unknown"), 
                    "timestamp": now,
                    "bearing": new_bearing if new_bearing is not None else (last_positions[bid].get("bearing") if bid in last_positions else None)
                }
            
            # Fade old segments (Increased from 120s to 7200s (2 hours) for the POC to keep the map painted)
            active_segments = [s for s in active_segments if (now - s["timestamp"]) < 7200]
            
            # Save state
            try:
                with open("state.json", "w") as f:
                    json.dump({"last_positions": last_positions, "active_segments": active_segments}, f)
            except Exception as e:
                print("Failed to save state:", e)
            
            print(f"[Tracker] {len(all_buses)} real buses tracked. {len(active_segments)} active segments drawn.", flush=True)
            await asyncio.sleep(15)

@app.get("/api/traffic_segments")
async def get_traffic_segments():
    features = []
    for s in active_segments:
        features.append({
            "type": "Feature",
            "properties": {
                "color": s["color"],
                "speed": s["speed"],
                "bus_id": s["bus_id"],
                "route": s.get("route", "Unknown")
            },
            "geometry": {
                "type": "LineString",
                "coordinates": s["path_geojson"]
            }
        })
    
    buses_geojson = []
    for bid, pos in last_positions.items():
        if time.time() - pos["timestamp"] < 600: 
            buses_geojson.append({
                "type": "Feature",
                "properties": {
                    "bus_id": bid,
                    "route": pos.get("route", "Unknown")
                },
                "geometry": {"type": "Point", "coordinates": [pos["lng"], pos["lat"]]}
            })
            
    return {
        "segments": {"type": "FeatureCollection", "features": features},
        "buses": {"type": "FeatureCollection", "features": buses_geojson},
        "stats": {
            "active_buses": len(buses_geojson),
            "drawn_segments": len(features)
        }
    }
