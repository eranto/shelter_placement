"""
Suggest capacity for each final shelter based on estimated wartime road traffic.

Methodology:
  - Wartime traffic is assumed to be 10% of normal AADT (people avoid roads during conflict).
  - Peak hour volume = 9% of daily AADT (standard Israeli road planning factor).
  - Alert window varies by location:
      · Within 15 km of Lebanon or Gaza border → 4 minutes (240 s)
      · All other areas                        → 5 minutes (300 s)
  - Vehicles within the driveable distance in that window (per direction) can reach
    the shelter in time.
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

# ── Alert window parameters ───────────────────────────────────────────────────
BORDER_ALERT_SECONDS   = 240   # 4 minutes — within 15 km of Lebanon or Gaza border
STANDARD_ALERT_SECONDS = 300   # 5 minutes — everywhere else
NEAR_BORDER_KM         = 15.0  # threshold

WARTIME_FRACTION   = 0.10  # 10% of normal traffic remains on roads during conflict
PEAK_HOUR_FRAC     = 0.09  # peak hour = 9% of daily AADT
PEOPLE_PER_VEHICLE = 1.3

STANDARD_SIZES = [6, 12, 20, 30, 50]

# Speed by highway type (km/h) — fallback when no maxspeed tag is present
HIGHWAY_SPEED = {
    'motorway': 100,
    'trunk':     90,
    'primary':   80,
    'secondary': 70,
}
DEFAULT_SPEED = 80

# ── Border polylines ──────────────────────────────────────────────────────────
# Approximate Israel–Lebanon Green Line (coast → Golan corner)
LEBANON_BORDER = [
    (33.07, 34.97),
    (33.09, 35.10),
    (33.11, 35.20),
    (33.15, 35.35),
    (33.20, 35.50),
    (33.27, 35.65),
]

# Approximate Gaza Strip eastern + northern boundary
GAZA_BORDER = [
    (31.61, 34.28),
    (31.61, 34.58),
    (31.42, 34.53),
    (31.22, 34.37),
]

# ── Border distance helpers ───────────────────────────────────────────────────
def _dist_pt_to_seg(plat, plon, alat, alon, blat, blon):
    """Flat-earth distance (km) from point P to line segment A→B."""
    R_lat = 111.0
    R_lon = 111.0 * math.cos(math.radians((alat + blat) / 2))
    px = (plon - alon) * R_lon
    py = (plat - alat) * R_lat
    dx = (blon - alon) * R_lon
    dy = (blat - alat) * R_lat
    seg2 = dx * dx + dy * dy
    if seg2 < 1e-10:
        return math.sqrt(px * px + py * py)
    t = max(0.0, min(1.0, (px * dx + py * dy) / seg2))
    ex = t * dx - px
    ey = t * dy - py
    return math.sqrt(ex * ex + ey * ey)

def _min_dist_to_polyline(lat, lon, pts):
    return min(
        _dist_pt_to_seg(lat, lon, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
        for i in range(len(pts) - 1)
    )

def alert_seconds_for(lat, lon):
    """Return 240 s if within NEAR_BORDER_KM of Lebanon or Gaza, else 300 s."""
    d_leb = _min_dist_to_polyline(lat, lon, LEBANON_BORDER)
    d_gaz = _min_dist_to_polyline(lat, lon, GAZA_BORDER)
    if min(d_leb, d_gaz) <= NEAR_BORDER_KM:
        return BORDER_ALERT_SECONDS
    return STANDARD_ALERT_SECONDS

# ── Capacity calculation ──────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def round_up_to_standard(n):
    """Map estimated catchment population to a shelter capacity tier.

    Thresholds are set so that 12p is the most common outcome (typical road),
    6p covers genuinely low-traffic rural roads, and larger sizes are reserved
    for high-AADT corridors.
    """
    if n <=  9: return 6
    if n <= 16: return 12
    if n <= 24: return 20
    if n <= 40: return 30
    return 50

def suggest_capacity(aadt, highway_type, maxspeed_str, alert_secs):
    try:
        speed_kmh = float(maxspeed_str) if maxspeed_str else None
    except ValueError:
        speed_kmh = None
    if not speed_kmh:
        speed_kmh = HIGHWAY_SPEED.get(highway_type, DEFAULT_SPEED)

    catchment_km = speed_kmh * (alert_secs / 3600)
    peak_flow_per_hour_per_dir = aadt * WARTIME_FRACTION * PEAK_HOUR_FRAC
    vehicles_in_catchment = peak_flow_per_hour_per_dir * (catchment_km / speed_kmh) * 2
    people = vehicles_in_catchment * PEOPLE_PER_VEHICLE
    return people, round_up_to_standard(people), speed_kmh, catchment_km

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
with open(HERE / "shelters_priority_final.csv", newline='', encoding='utf-8-sig') as f:
    shelters = list(csv.DictReader(f))
print(f"  {len(shelters)} shelters loaded.")

# ── Match each shelter to nearest road segment ────────────────────────────────
print("Computing capacities ...")
results = []
near_border_count = 0
for shelter in shelters:
    slat = float(shelter['lat'])
    slon = float(shelter['lon'])

    nearest = min(segments, key=lambda s: haversine_km(slat, slon, s['lat'], s['lon']))
    dist_to_seg = haversine_km(slat, slon, nearest['lat'], nearest['lon'])

    alert_secs = alert_seconds_for(slat, slon)
    if alert_secs == BORDER_ALERT_SECONDS:
        near_border_count += 1

    people, capacity, speed, catchment = suggest_capacity(
        nearest['aadt'], nearest['highway_type'], nearest['maxspeed'], alert_secs
    )

    results.append({
        **shelter,
        'matched_route':                nearest['route_ref'],
        'matched_highway_type':         nearest['highway_type'],
        'road_speed_kmh':               int(speed),
        'catchment_per_dir_km':         round(catchment, 2),
        'aadt_normal':                  nearest['aadt'],
        'aadt_wartime':                 round(nearest['aadt'] * WARTIME_FRACTION),
        'estimated_people_in_catchment': round(people, 1),
        'suggested_capacity':           capacity,
        'alert_seconds':                alert_secs,
        'nearest_seg_dist_km':          round(dist_to_seg, 2),
    })

# ── Summary ───────────────────────────────────────────────────────────────────
from collections import Counter
cap_dist = Counter(r['suggested_capacity'] for r in results)
print(f"\nCapacity distribution across {len(results)} shelters:")
for size in STANDARD_SIZES:
    count = cap_dist.get(size, 0)
    bar = '█' * (count // 2)
    print(f"  {size:>3} people: {count:>3}  {bar}")
print(f"\nNear-border shelters (4-min window): {near_border_count}")
print(f"Standard shelters (5-min window):    {len(results) - near_border_count}")

print(f"\nSample (top 10 by rank):")
print(f"  {'Rank':>4}  {'Road':<25}  {'Zone':<10}  {'AlertSec':>8}  {'AADT(war)':>9}  {'People':>6}  {'Cap':>3}")
for r in results[:10]:
    print(f"  {r['rank']:>4}  {r['road']:<25}  {r['zone']:<10}  "
          f"{r['alert_seconds']:>8}  {r['aadt_wartime']:>9,}  "
          f"{r['estimated_people_in_catchment']:>6.1f}  {r['suggested_capacity']:>3}")

# ── Write output ──────────────────────────────────────────────────────────────
out_fields = [
    'rank', 'lat', 'lon', 'road', 'zone',
    'composite_score', 'nearby_alerts_marapr2026',
    'matched_route', 'matched_highway_type',
    'road_speed_kmh', 'catchment_per_dir_km',
    'aadt_normal', 'aadt_wartime',
    'estimated_people_in_catchment', 'suggested_capacity',
    'alert_seconds',
    'lanes_weight', 'nearest_seg_dist_km',
]

out_path = HERE / "shelters_with_capacity.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=out_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(results)

print(f"\nWrote {len(results)} rows → {out_path.name}")
