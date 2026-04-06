"""
Export shelter datasets to CSV files.

Outputs:
  shelters_base.csv          — all shelter locations with road/risk info
  shelters_aadt_ranked.csv   — ranked by estimated daily traffic (AADT)
  shelters_alert_ranked.csv  — ranked by missile alert density (Oct 7 2023–present)
  shelters_combined.csv      — all metrics merged, sorted by alert rank
"""

import pickle, json, math, csv
from pathlib import Path

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── Load shelter points ────────────────────────────────────────────────────────
shelter_points, final_max = pickle.load(open(HERE / "shelter_points_traffic.pkl", "rb"))
# (lat, lon, risk, cap_w, road_name)
print(f"Loaded {len(shelter_points)} shelter points.")

# ── AADT model (same as road_shelters_traffic.py) ─────────────────────────────
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

def base_aadt(lanes):
    l = lanes if lanes else 2
    return {1: 4_000, 2: 8_000, 3: 13_000, 4: 18_000}.get(min(int(l), 4), 18_000)

def shelter_aadt(road_name, cap_w):
    aadt = ROUTE_AADT.get(str(road_name))
    if aadt is None and ';' in str(road_name):
        aadt = ROUTE_AADT.get(str(road_name).split(';')[0])
    if aadt is None:
        # Infer from cap_w (lanes proxy): 1.0→2 lanes, 1.5→2, 2.0→3, 2.5→4
        lane_est = {1.0: 2, 1.5: 2, 2.0: 3, 2.5: 4, 3.0: 4}.get(round(cap_w * 2) / 2, 2)
        aadt = base_aadt(lane_est)
    return aadt

# ── Alert scoring (same as shelter_alert_ranking.py) ──────────────────────────
RADIUS_KM = 15.0

geo = json.load(open("/tmp/geocoded_cities.json"))
alert_locations = [
    (float(v['lat']), float(v['lon']), v['alerts'], city)
    for city, v in geo.items()
    if v.get('lat') is not None
]
total_alerts_available = sum(v['alerts'] for v in geo.values() if v.get('lat'))
total_alerts_all       = sum(v['alerts'] for v in geo.values())
print(f"Alert coverage: {total_alerts_available:,}/{total_alerts_all:,} "
      f"({100*total_alerts_available/total_alerts_all:.1f}%)")

def seg_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat**2 + dlon**2)

# ── Build combined record per shelter ────────────────────────────────────────
print("Computing AADT and alert scores...")
records = []
for lat, lon, risk, cap_w, rname in shelter_points:
    aadt = shelter_aadt(rname, cap_w)
    nearby_alerts = sum(
        alerts
        for clat, clon, alerts, _ in alert_locations
        if seg_km((lat, lon), (clat, clon)) <= RADIUS_KM
    )
    records.append({
        'lat': float(lat),
        'lon': float(lon),
        'road': rname,
        'risk_score': round(float(risk), 2),
        'lanes_weight': round(float(cap_w), 1),
        'aadt_vehicles_per_day': aadt,
        'nearby_alerts_15km': nearby_alerts,
    })

print(f"Scored {len(records)} shelters.")

# ── Rank each dimension ────────────────────────────────────────────────────────
aadt_ranked   = sorted(records, key=lambda r: r['aadt_vehicles_per_day'], reverse=True)
alert_ranked  = sorted(records, key=lambda r: r['nearby_alerts_15km'], reverse=True)
base_order    = sorted(records, key=lambda r: r['risk_score'], reverse=True)

# Add rank columns
for rank, r in enumerate(aadt_ranked, 1):
    r['aadt_rank'] = rank
for rank, r in enumerate(alert_ranked, 1):
    r['alert_rank'] = rank

# ── CSV helpers ───────────────────────────────────────────────────────────────
FIELDS_BASE = ['lat', 'lon', 'road', 'risk_score', 'lanes_weight']
FIELDS_AADT = FIELDS_BASE + ['aadt_vehicles_per_day', 'aadt_rank']
FIELDS_ALERT = FIELDS_BASE + ['nearby_alerts_15km', 'alert_rank']
FIELDS_ALL  = ['alert_rank', 'aadt_rank', 'lat', 'lon', 'road',
               'risk_score', 'lanes_weight', 'aadt_vehicles_per_day',
               'nearby_alerts_15km']

def write_csv(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f"  Wrote {len(rows)} rows → {path.name}")

# ── Write files ───────────────────────────────────────────────────────────────
write_csv(HERE / "shelters_base.csv",          base_order,  FIELDS_BASE)
write_csv(HERE / "shelters_aadt_ranked.csv",   aadt_ranked, FIELDS_AADT)
write_csv(HERE / "shelters_alert_ranked.csv",  alert_ranked, FIELDS_ALERT)
write_csv(HERE / "shelters_combined.csv",
          sorted(records, key=lambda r: r.get('alert_rank', 9999)),
          FIELDS_ALL)

print("\nDone. Files written:")
for name in ["shelters_base.csv", "shelters_aadt_ranked.csv",
             "shelters_alert_ranked.csv", "shelters_combined.csv"]:
    size = (HERE / name).stat().st_size
    print(f"  {name:40s}  {size:,} bytes")
