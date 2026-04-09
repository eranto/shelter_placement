"""
Build an enriched road segment dataset from existing source data.

For each OSM road segment (from road_segments.csv) compute:
  - aadt_vehicles_per_day    : estimated daily vehicle count (route lookup + lanes fallback)
  - nearby_alerts_15km       : sum of missile alerts for geocoded cities within 15 km
  - dist_to_north_border_km  : distance to the north conflict zone boundary (lat 33.05°)
  - dist_to_gaza_border_km   : distance to the Gaza envelope zone boundary
  - border_closeness_km      : min of the two border distances (0 = inside a border zone)
  - alert_score              : nearby_alerts normalised to [0, 1]
  - border_score             : 1 / (1 + border_closeness_km / 30), higher = closer to border
  - risk_score               : 0.6 * alert_score + 0.4 * border_score  [0, 1]

Inputs:
  road_segments.csv          (route_ref, highway_type, lanes, maxspeed_kmh, length_km,
                               midpoint_lat, midpoint_lon)
  alert_areas_geocoded.csv   (area_name_hebrew, lat, lon, alerts_since_oct7_2023, geocoded)

Output:
  road_segments_enriched.csv
"""

import csv, math
from pathlib import Path

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

ALERT_RADIUS_KM = 15.0

# ── AADT lookup by route reference ────────────────────────────────────────────
ROUTE_AADT = {
    '20':  105_000, '2':    75_000, '1':    55_000, '4':    40_000,
    '6':    48_000, '3':    30_000, '40':   22_000, '44':   18_000,
    '22':   35_000, '65':   24_000, '79':   18_000, '77':   19_000,
    '75':   14_000, '85':   15_000, '70':   20_000, '90':    9_000,
    '90;1':  9_000, '25':    7_000, '31':    6_500, '40;1':  8_000,
    '232':   7_000, '34':    8_500, '35':   11_000, '99':    5_000,
    '978':   3_500, '899':   3_500, '38':   14_000, '60':   16_000,
    '89':    9_000, '60;6': 16_000,
}

LANES_TO_AADT = {1: 4_000, 2: 8_000, 3: 13_000, 4: 18_000}

def segment_aadt(route_ref, lanes_str):
    aadt = ROUTE_AADT.get(str(route_ref))
    if aadt is None and ';' in str(route_ref):
        aadt = ROUTE_AADT.get(str(route_ref).split(';')[0])
    if aadt is None:
        try:
            lanes = max(1, min(int(float(lanes_str)), 4)) if lanes_str else 2
        except (ValueError, TypeError):
            lanes = 2
        aadt = LANES_TO_AADT.get(lanes, 8_000)
    return aadt

# ── Distance helpers ──────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def dist_to_north_border(lat, lon):
    """Distance in km south of the north conflict zone boundary (lat 33.05°)."""
    if lat >= 33.05:
        return 0.0
    return (33.05 - lat) * 111.0

def dist_to_gaza_border(lat, lon):
    """
    Distance in km to the Gaza envelope zone boundary.
    Zone is defined as lat < 31.60° AND lon < 34.90°.
    Points inside the zone return 0.
    """
    if lat <= 31.60 and lon <= 34.90:
        return 0.0
    # Nearest point on the zone boundary
    clamp_lat = min(lat, 31.60)
    clamp_lon = min(lon, 34.90)
    return haversine_km(lat, lon, clamp_lat, clamp_lon)

# ── Load alert cities ─────────────────────────────────────────────────────────
print("Loading alert data ...")
alert_cities = []
with open(HERE / "alert_areas_geocoded.csv", newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row.get('geocoded') == 'yes' and row['lat'] and row['lon']:
            alert_cities.append((
                float(row['lat']),
                float(row['lon']),
                int(row['alerts_since_oct7_2023']),
            ))
print(f"  {len(alert_cities)} geocoded alert cities loaded.")

# ── Load road segments ────────────────────────────────────────────────────────
print("Loading road segments ...")
segments = []
with open(HERE / "road_segments.csv", newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        try:
            lat = float(row['midpoint_lat'])
            lon = float(row['midpoint_lon'])
        except (ValueError, KeyError):
            continue
        segments.append({
            'route_ref':    row.get('route_ref', ''),
            'highway_type': row.get('highway_type', ''),
            'lanes':        row.get('lanes', ''),
            'maxspeed_kmh': row.get('maxspeed_kmh', ''),
            'length_km':    row.get('length_km', ''),
            'midpoint_lat': lat,
            'midpoint_lon': lon,
        })
print(f"  {len(segments)} segments loaded.")

# ── Compute metrics for each segment ─────────────────────────────────────────
print("Computing metrics ...")
for i, seg in enumerate(segments):
    if i % 2000 == 0:
        print(f"  {i}/{len(segments)} ...")
    lat, lon = seg['midpoint_lat'], seg['midpoint_lon']

    seg['aadt_vehicles_per_day'] = segment_aadt(seg['route_ref'], seg['lanes'])

    seg['nearby_alerts_15km'] = sum(
        alerts
        for clat, clon, alerts in alert_cities
        if haversine_km(lat, lon, clat, clon) <= ALERT_RADIUS_KM
    )

    north_dist = dist_to_north_border(lat, lon)
    gaza_dist  = dist_to_gaza_border(lat, lon)
    seg['dist_to_north_border_km'] = round(north_dist, 1)
    seg['dist_to_gaza_border_km']  = round(gaza_dist, 1)
    seg['border_closeness_km']     = round(min(north_dist, gaza_dist), 1)

# ── Normalise and compute risk score ─────────────────────────────────────────
max_alerts = max(s['nearby_alerts_15km'] for s in segments) or 1

for seg in segments:
    alert_score  = seg['nearby_alerts_15km'] / max_alerts
    border_score = 1.0 / (1.0 + seg['border_closeness_km'] / 30.0)
    seg['alert_score']  = round(alert_score, 4)
    seg['border_score'] = round(border_score, 4)
    seg['risk_score']   = round(0.6 * alert_score + 0.4 * border_score, 4)

# ── Write output ──────────────────────────────────────────────────────────────
OUT_FIELDS = [
    'route_ref', 'highway_type', 'lanes', 'maxspeed_kmh', 'length_km',
    'midpoint_lat', 'midpoint_lon',
    'aadt_vehicles_per_day',
    'nearby_alerts_15km',
    'dist_to_north_border_km',
    'dist_to_gaza_border_km',
    'border_closeness_km',
    'alert_score',
    'border_score',
    'risk_score',
]

out_path = HERE / "road_segments_enriched.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction='ignore')
    w.writeheader()
    w.writerows(segments)

print(f"\nDone. Wrote {len(segments)} rows → {out_path.name}")
print(f"  Max nearby alerts: {max_alerts:,}")
print(f"  Risk score range:  {min(s['risk_score'] for s in segments):.4f} – {max(s['risk_score'] for s in segments):.4f}")
