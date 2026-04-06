"""
Export intermediate/source datasets to CSV files in the project folder.

Outputs:
  alert_areas_geocoded.csv   — each alert area/city: name, lat, lon, total alerts since Oct 7 2023
  alert_areas_all.csv        — all 1,571 alert area names with counts (incl. ungeocoded)
  road_segments.csv          — OSM road segments: route, highway type, lanes, maxspeed, length_km
  alerts_raw_since_oct7.csv  — raw alert log since Oct 7 2023 (one row per alert event)
"""

import json, csv, pickle, math
from pathlib import Path
import datetime

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── 1. Alert areas — geocoded ─────────────────────────────────────────────────
print("Writing alert_areas_geocoded.csv ...")
geo = json.load(open("/tmp/geocoded_cities.json"))

rows = []
for city, v in geo.items():
    rows.append({
        'area_name_hebrew': city,
        'lat': v.get('lat', ''),
        'lon': v.get('lon', ''),
        'alerts_since_oct7_2023': v['alerts'],
        'geocoded': 'yes' if v.get('lat') else 'no',
    })
rows.sort(key=lambda r: -r['alerts_since_oct7_2023'])

with open(HERE / "alert_areas_geocoded.csv", 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['area_name_hebrew','lat','lon',
                                      'alerts_since_oct7_2023','geocoded'])
    w.writeheader()
    w.writerows(rows)

geocoded_n = sum(1 for r in rows if r['geocoded'] == 'yes')
print(f"  {len(rows)} areas ({geocoded_n} geocoded) → alert_areas_geocoded.csv")

# ── 2. Alert area counts — full list (all 1,571 base names) ───────────────────
print("Writing alert_areas_all.csv ...")
city_counts = json.load(open("/tmp/city_alert_counts.json"))

rows2 = [{'area_name_hebrew': city, 'alerts_since_oct7_2023': cnt}
         for city, cnt in city_counts.items()]
rows2.sort(key=lambda r: -r['alerts_since_oct7_2023'])

with open(HERE / "alert_areas_all.csv", 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['area_name_hebrew', 'alerts_since_oct7_2023'])
    w.writeheader()
    w.writerows(rows2)
print(f"  {len(rows2)} areas → alert_areas_all.csv")

# ── 3. Road segments ──────────────────────────────────────────────────────────
print("Writing road_segments.csv ...")
segs = pickle.load(open(HERE / "osm_roads_traffic_cache.pkl", 'rb'))

def seg_km(geom):
    """Approximate length of a segment from its geometry."""
    if not geom or len(geom) < 2:
        return 0.0
    total = 0.0
    for i in range(len(geom) - 1):
        p1, p2 = geom[i], geom[i+1]
        dlat = (p2[0] - p1[0]) * 111.0
        dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
        total += math.sqrt(dlat**2 + dlon**2)
    return round(total, 3)

def midpoint(geom):
    if not geom:
        return None, None
    mid = geom[len(geom)//2]
    return round(mid[0], 5), round(mid[1], 5)

seg_rows = []
for s in segs:
    lat, lon = midpoint(s.get('geom', []))
    seg_rows.append({
        'route_ref':    s.get('name', ''),
        'highway_type': s.get('highway', ''),
        'lanes':        s.get('lanes', ''),
        'maxspeed_kmh': s.get('maxspeed', ''),
        'length_km':    seg_km(s.get('geom', [])),
        'midpoint_lat': lat or '',
        'midpoint_lon': lon or '',
    })

seg_rows.sort(key=lambda r: (r['route_ref'], r['highway_type']))

with open(HERE / "road_segments.csv", 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['route_ref','highway_type','lanes',
                                      'maxspeed_kmh','length_km',
                                      'midpoint_lat','midpoint_lon'])
    w.writeheader()
    w.writerows(seg_rows)

total_km = sum(r['length_km'] for r in seg_rows)
print(f"  {len(seg_rows)} segments, {total_km:,.0f} km total → road_segments.csv")

# ── 4. Raw alert log since Oct 7 2023 ─────────────────────────────────────────
print("Writing alerts_raw_since_oct7.csv ...")
OCT7 = datetime.date(2023, 10, 7)

out_path = HERE / "alerts_raw_since_oct7.csv"
count = 0
with open("/tmp/israel_alerts.csv", encoding='utf-8') as fin, \
     open(out_path, 'w', newline='', encoding='utf-8-sig') as fout:

    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout,
        fieldnames=['alertDate','category_desc','area_names_hebrew'],
        extrasaction='ignore')
    writer.writeheader()

    for row in reader:
        try:
            d = datetime.date.fromisoformat(row['alertDate'][:10])
        except (ValueError, KeyError):
            continue
        if d < OCT7:
            continue
        writer.writerow({
            'alertDate':           row['alertDate'][:16],   # drop seconds
            'category_desc':       row.get('category_desc', ''),
            'area_names_hebrew':   row.get('data', ''),
        })
        count += 1

print(f"  {count:,} alert events → alerts_raw_since_oct7.csv")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\nAll files written:")
for name in ["alert_areas_geocoded.csv", "alert_areas_all.csv",
             "road_segments.csv", "alerts_raw_since_oct7.csv"]:
    p = HERE / name
    if p.exists():
        print(f"  {name:40s}  {p.stat().st_size:>10,} bytes")
