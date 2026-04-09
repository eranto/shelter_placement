"""
Export the final shelter placement CSV with all details shown on the map,
including alert-adjusted capacity and unit cost.

Output: shelters_final_placements.csv
"""

import csv, math, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent))
from israel_1967_filter import in_1967_israel

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── Capacity upgrade logic (mirrors create_budget_excel_v2.py) ────────────────
TIERS     = [6, 12, 20, 30, 50]
COSTS     = {6: 73_000, 12: 100_000, 20: 150_000, 30: 200_000, 50: 250_000}
ZONE_LABEL = {'north': 'North border', 'gaza': 'Gaza envelope', 'standard': 'Standard'}

def upgrade_cap(cap, n):
    idx = TIERS.index(cap)
    return TIERS[min(idx + n, len(TIERS) - 1)]

def adjusted_capacity(cap, alerts, zone):
    if alerts > 40_000:
        cap = upgrade_cap(cap, 2)
    elif alerts > 20_000:
        cap = upgrade_cap(cap, 1)
    elif alerts > 10_000 and cap == 6:
        cap = 12
    if zone in ('north', 'gaza') and cap < 12:
        cap = 12
    return cap

def upgrade_reason(orig_cap, alerts, zone):
    reasons = []
    if alerts > 40_000:
        reasons.append(f'alerts>40K (+2 tiers)')
    elif alerts > 20_000:
        reasons.append(f'alerts>20K (+1 tier)')
    elif alerts > 10_000 and orig_cap == 6:
        reasons.append(f'alerts>10K (6→12)')
    if zone in ('north', 'gaza') and orig_cap < 12:
        reasons.append(f'{zone} zone (min 12)')
    return '; '.join(reasons) if reasons else ''

# ── Load base data ────────────────────────────────────────────────────────────
rows = list(csv.DictReader(open(HERE / "shelters_with_capacity.csv", encoding='utf-8')))
print(f"Loaded {len(rows)} shelters.")

# ── Build output records ──────────────────────────────────────────────────────
out = []
for r in rows:
    lat_f = float(r['lat'])
    lon_f = float(r['lon'])
    if not in_1967_israel(lat_f, lon_f):
        continue

    alerts   = int(r['nearby_alerts_marapr2026']) if r.get('nearby_alerts_marapr2026') else 0
    zone     = r['zone']
    orig_cap = int(r['suggested_capacity'])
    new_cap  = adjusted_capacity(orig_cap, alerts, zone)
    reason   = upgrade_reason(orig_cap, alerts, zone)

    out.append({
        'rank':                         r['rank'],
        'lat':                          r['lat'],
        'lon':                          r['lon'],
        'road':                         r['road'],
        'zone':                         ZONE_LABEL.get(zone, zone),
        'composite_score':              r['composite_score'],
        'nearby_alerts_marapr2026':     alerts,
        'highway_type':                 r['matched_highway_type'],
        'road_speed_kmh':               r['road_speed_kmh'],
        'catchment_per_dir_km':         r['catchment_per_dir_km'],
        'aadt_normal':                  r['aadt_normal'],
        'aadt_wartime':                 r['aadt_wartime'],
        'estimated_people_in_catchment': r['estimated_people_in_catchment'],
        'base_capacity':                orig_cap,
        'suggested_capacity':           new_cap,
        'capacity_upgraded':            'yes' if new_cap != orig_cap else 'no',
        'upgrade_reason':               reason,
    })

# ── Summary ───────────────────────────────────────────────────────────────────
upgraded  = sum(1 for r in out if r['capacity_upgraded'] == 'yes')
cap_dist  = Counter(r['suggested_capacity'] for r in out)
print(f"Upgraded: {upgraded} shelters")
print(f"Capacity distribution: { {k: cap_dist[k] for k in TIERS} }")

# ── Write CSV ─────────────────────────────────────────────────────────────────
fields = [
    'rank', 'lat', 'lon', 'road', 'zone', 'composite_score',
    'nearby_alerts_marapr2026', 'highway_type', 'road_speed_kmh',
    'catchment_per_dir_km', 'aadt_normal', 'aadt_wartime',
    'estimated_people_in_catchment',
    'base_capacity', 'suggested_capacity', 'capacity_upgraded', 'upgrade_reason',
]

out_path = HERE / "shelters_final_placements.csv"
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(out)

print(f"Wrote {len(out)} rows → {out_path.name}")
