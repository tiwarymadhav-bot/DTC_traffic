# Delhi Bus Tracking System - Route 85
## DTC Route 85: Anand Vihar ISBT to Punjabi Bagh Terminal

---

## Quick Start

`
# Step 1: Bus Stop Data (already done - generates data/route_85_stops.json)
python step1_collect_bus_stops.py

# Step 2: Download OSM Road Network (takes 3-5 mins - saves to data/)
python step2_download_osm.py

# Step 3: Fetch Live Bus Positions (uses dtcbusroutes.in API)
python step3_live_bus_tracker.py

# Step 4: Generate Interactive Map (opens in browser)
python step4_generate_map.py
Then open: route_85_map.html in your browser
`

---

## Project Structure

`
delhi_bus_tracking/
|-- step1_collect_bus_stops.py    # Collects 52 stop coords
|-- step2_download_osm.py         # Downloads OSM road network
|-- step3_live_bus_tracker.py     # Fetches live bus positions from API
|-- step4_generate_map.py         # Generates interactive Folium map
|-- route_85_map.html             # << OPEN THIS IN BROWSER
|-- data/
    |-- route_85_stops.json       # 52 stop lat/lon coords
    |-- live_snapshot.json        # Latest bus positions
    |-- osm_road_network.gpkg     # OSM roads (GeoPackage - 2 layers)
    |-- osm_edges.geojson         # OSM road edges (GeoJSON)
    |-- osm_road_graph.graphml    # Road graph for NetworkX routing
`

---

## Live Bus API

Found via browser DevTools (Network tab):

`
GET https://www.dtcbusroutes.in/api/buses/?route=85
`

### API Response Format:
`json
{
  "buses": [
    {
      "id": "DL51EV1777",
      "lat": 28.674114227294922,
      "lng": 77.287109375,
      "route": "85",
      "route_id": "2141",
      "ac": "ac",
      "agency": "DTC"
    }
  ],
  "count": 11
}
`

---

## Route 85 Summary

| Field       | Value                              |
|-------------|------------------------------------|
| Route No    | 85                                 |
| From        | Anand Vihar ISBT                   |
| To          | Punjabi Bagh Terminal              |
| Total Stops | 52                                 |
| Trips/Day   | 98                                 |
| Service     | 12:05 AM - 11:15 PM               |
| Agency      | DTC (Delhi Transport Corporation)  |

---

## Traffic Classification

| Speed       | Status      | Color  |
|-------------|-------------|--------|
| < 5 km/h    | Heavy Jam   | Red    |
| 5-15 km/h   | Moderate    | Orange |
| 15-30 km/h  | Slow        | Yellow |
| > 30 km/h   | Free Flow   | Green  |

---

## OSM Data Usage

- **Source**: OpenStreetMap via Overpass API (osmnx)
- **Network Type**: Drive (roads + edges only)
- **Stored as**: GeoPackage (.gpkg) + GeoJSON + GraphML
- **Use**: Road edge display, map-matching bus GPS, routing

---

## Map Features

- Animated route line (Anand Vihar → Punjabi Bagh)
- 52 bus stop markers with stop names
- Live bus positions with direction arrows
- Traffic color coding per bus
- Pop-up details: speed, heading, nearest stop, distance
- Layer toggle (stops/buses on/off)
- Traffic legend
