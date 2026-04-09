"""
Export the final shelter placement CSV.

Capacity tiers are assigned by traffic rank in shelter_capacity.py (30/30/40).
This script applies only the strict border filter and translates zone labels.

Output: shelters_final_placements.csv
"""

import csv, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent))
from filter_shelters_borders import strict_in_israel

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

TIERS      = [6, 12, 20]
ZONE_LABEL = {'north': 'North border', 'gaza': 'Gaza envelope', 'standard': 'Standard'}

# ── Load base data ────────────────────────────────────────────────────────────
rows = list(csv.DictReader(open(HERE / "shelters_with_capacity.csv", encoding='utf-8')))
print(f"Loaded {len(rows)} shelters.")

# ── Build output records ──────────────────────────────────────────────────────
out = []
for r in rows:
    lat_f = float(r['lat'])
    lon_f = float(r['lon'])
    ok, _ = strict_in_israel(lat_f, lon_f)
    if not ok:
        continue

    alerts = int(r['nearby_alerts_marapr2026']) if r.get('nearby_alerts_marapr2026') else 0
    zone   = r['zone']
    cap    = int(r['suggested_capacity'])

    out.append({
        'rank':                          r['rank'],
        'lat':                           r['lat'],
        'lon':                           r['lon'],
        'road':                          r['road'],
        'zone':                          ZONE_LABEL.get(zone, zone),
        'composite_score':               r['composite_score'],
        'nearby_alerts_marapr2026':      alerts,
        'highway_type':                  r['matched_highway_type'],
        'road_speed_kmh':                r['road_speed_kmh'],
        'catchment_per_dir_km':          r['catchment_per_dir_km'],
        'aadt_normal':                   r['aadt_normal'],
        'aadt_wartime':                  r['aadt_wartime'],
        'estimated_people_in_catchment': r['estimated_people_in_catchment'],
        'suggested_capacity':            cap,
        'alert_seconds':                 r.get('alert_seconds', ''),
    })

# ── Summary ───────────────────────────────────────────────────────────────────
cap_dist = Counter(r['suggested_capacity'] for r in out)
print(f"Capacity distribution: { {k: cap_dist[k] for k in TIERS} }")

# ── Write CSV ─────────────────────────────────────────────────────────────────
fields = [
    'rank', 'lat', 'lon', 'road', 'zone', 'composite_score',
    'nearby_alerts_marapr2026', 'highway_type', 'road_speed_kmh',
    'catchment_per_dir_km', 'aadt_normal', 'aadt_wartime',
    'estimated_people_in_catchment', 'suggested_capacity', 'alert_seconds',
]

out_path = HERE / "shelters_final_placements.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(out)

print(f"Wrote {len(out)} rows → {out_path.name}")
