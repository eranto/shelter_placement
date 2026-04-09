"""
Suggest capacity for each final shelter based on estimated wartime road traffic.

Methodology:
  - Wartime traffic is assumed to be 10% of normal AADT (people avoid roads during conflict).
  - Peak hour volume = 9% of daily AADT (standard Israeli road planning factor).
  - Alert catchment = distance driveable in 90 seconds at road speed (e.g. 100 km/h → 2.5 km).
    All vehicles within that distance in either direction can reach the shelter in time.
  - People per vehicle = 1.3 (wartime travel is mostly solo).
  - Suggested capacity is rounded up to the nearest standard shelter size: 6, 12, 20, 30, 50.

For each shelter, the nearest road segment from road_segments_enriched.csv is used
to determine AADT, speed, and highway type.

Output:
  shelters_with_capacity.csv
"""

import csv, math
from pathlib import Path

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── Parameters ────────────────────────────────────────────────────────────────
WARTIME_FRACTION  = 0.10   # 10% of normal traffic remains on roads
PEAK_HOUR_FRAC    = 0.09   # peak hour = 9% of daily AADT
PEOPLE_PER_VEHICLE = 1.3
ALERT_SECONDS     = 90     # standard Israeli alert-to-shelter window

STANDARD_SIZES = [6, 12, 20, 30, 50]  # available shelter capacities (people)

# Speed by highway type (km/h) — used to estimate alert catchment distance
HIGHWAY_SPEED = {
    'motorway': 100,
    'trunk':     90,
    'primary':   80,
    'secondary': 70,
}
DEFAULT_SPEED = 80

# ── Helpers ───────────────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def round_up_to_standard(n):
    for size in STANDARD_SIZES:
        if n <= size:
            return size
    return STANDARD_SIZES[-1]  # cap at largest standard size

def suggest_capacity(aadt, highway_type, maxspeed_str):
    # Determine speed
    try:
        speed_kmh = float(maxspeed_str) if maxspeed_str else None
    except ValueError:
        speed_kmh = None
    if not speed_kmh:
        speed_kmh = HIGHWAY_SPEED.get(highway_type, DEFAULT_SPEED)

    # Catchment distance per direction (km) in alert window
    catchment_km = speed_kmh * (ALERT_SECONDS / 3600)

    # Vehicles in catchment at wartime peak hour (both directions)
    peak_flow_per_hour_per_dir = aadt * WARTIME_FRACTION * PEAK_HOUR_FRAC
    vehicles_in_catchment = peak_flow_per_hour_per_dir * (catchment_km / speed_kmh) * 2

    # People
    people = vehicles_in_catchment * PEOPLE_PER_VEHICLE

    return people, round_up_to_standard(math.ceil(people)), speed_kmh, catchment_km

# ── Load road segments ────────────────────────────────────────────────────────
print("Loading road segments ...")
segments = []
with open(HERE / "road_segments_enriched.csv", newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        try:
            segments.append({
                'lat':          float(row['midpoint_lat']),
                'lon':          float(row['midpoint_lon']),
                'aadt':         int(row['aadt_vehicles_per_day']),
                'highway_type': row['highway_type'],
                'maxspeed':     row['maxspeed_kmh'],
                'route_ref':    row['route_ref'],
            })
        except (ValueError, KeyError):
            continue
print(f"  {len(segments)} segments loaded.")

# ── Load shelters ─────────────────────────────────────────────────────────────
print("Loading shelters ...")
shelters = []
with open(HERE / "shelters_priority_final.csv", newline='', encoding='utf-8-sig') as f:
    shelters = list(csv.DictReader(f))
print(f"  {len(shelters)} shelters loaded.")

# ── Match each shelter to nearest road segment ────────────────────────────────
print("Computing capacities ...")
results = []
for shelter in shelters:
    slat = float(shelter['lat'])
    slon = float(shelter['lon'])

    # Find nearest segment by midpoint distance
    nearest = min(segments, key=lambda s: haversine_km(slat, slon, s['lat'], s['lon']))
    dist_to_seg = haversine_km(slat, slon, nearest['lat'], nearest['lon'])

    people, capacity, speed, catchment = suggest_capacity(
        nearest['aadt'], nearest['highway_type'], nearest['maxspeed']
    )

    results.append({
        **shelter,
        'matched_route':       nearest['route_ref'],
        'matched_highway_type': nearest['highway_type'],
        'road_speed_kmh':      int(speed),
        'catchment_per_dir_km': round(catchment, 2),
        'aadt_normal':         nearest['aadt'],
        'aadt_wartime':        round(nearest['aadt'] * WARTIME_FRACTION),
        'estimated_people_in_catchment': round(people, 1),
        'suggested_capacity':  capacity,
        'nearest_seg_dist_km': round(dist_to_seg, 2),
    })

# ── Summary ───────────────────────────────────────────────────────────────────
from collections import Counter
cap_dist = Counter(r['suggested_capacity'] for r in results)
print(f"\nCapacity distribution across {len(results)} shelters:")
for size in STANDARD_SIZES:
    count = cap_dist.get(size, 0)
    bar = '█' * (count // 2)
    print(f"  {size:>3} people: {count:>3}  {bar}")

print(f"\nSample (top 10 by rank):")
print(f"  {'Rank':>4}  {'Road':<25}  {'Zone':<10}  {'AADT(war)':>9}  {'People':>6}  {'Cap':>3}")
for r in results[:10]:
    print(f"  {r['rank']:>4}  {r['road']:<25}  {r['zone']:<10}  "
          f"{r['aadt_wartime']:>9,}  {r['estimated_people_in_catchment']:>6.1f}  {r['suggested_capacity']:>3}")

# ── Write output ──────────────────────────────────────────────────────────────
out_fields = [
    'rank', 'lat', 'lon', 'road', 'zone',
    'composite_score', 'nearby_alerts_marapr2026',
    'matched_route', 'matched_highway_type',
    'road_speed_kmh', 'catchment_per_dir_km',
    'aadt_normal', 'aadt_wartime',
    'estimated_people_in_catchment', 'suggested_capacity',
    'lanes_weight', 'nearest_seg_dist_km',
]

out_path = HERE / "shelters_with_capacity.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=out_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)

print(f"\nWrote {len(results)} rows → {out_path.name}")
