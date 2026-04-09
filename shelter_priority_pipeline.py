"""
Pipeline: priority-zone placement → dedup → urban relocation → composite scoring → map + CSV.

Uses shelter_points_priority.pkl (5.0-min uniform standard).
Applies urban relocation (same logic as shelter_urban_relocate.py).
Composite ranking = 50% Mar-Apr 2026 alert density + 50% border proximity risk
  (border proximity = closeness to Lebanon border or Gaza Strip fence, max effect at 50 km).

Outputs:
  shelters_priority_final.html
  shelters_priority_final.csv
"""

import csv, json, math, pickle, sys
from pathlib import Path
from collections import defaultdict
import folium
from folium.plugins import MarkerCluster

sys.path.insert(0, str(Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")))
from filter_shelters_borders import in_1967_israel, filter_segment

HERE       = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")
CKPT       = HERE / "shelter_points_priority.pkl"
OSM_CACHE  = HERE / "osm_roads_traffic_cache.pkl"
GEO_FILE   = "/tmp/geocoded_cities.json"
ALERTS_CSV = "/tmp/israel_alerts.csv"

RADIUS_KM        = 15.0
MIN_DEDUP_KM     = 2.5
URBAN_RADIUS_KM  = 2.5
CITY_MIN_ALERTS  = 400
MIN_MOVE_KM      = 1.0
TARGET_MONTHS    = {'2026-03', '2026-04'}

# Priority zone boundaries (must match run_priority_placement.py)
TIME_PRIOR = 5.0
def is_priority_zone(lat, lon):
    if lat > 33.05: return 'north'
    if lat < 31.60 and lon < 34.90: return 'gaza'
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def dist_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

# ── Border proximity ──────────────────────────────────────────────────────────
# Lebanon border: coast (33.07, 35.07) → inland (33.27, 35.65)
LEBANON_BORDER = [(33.07, 35.07), (33.12, 35.20), (33.20, 35.40), (33.27, 35.65)]
# Gaza border: northern edge + eastern fence
GAZA_BORDER    = [(31.61, 34.28), (31.61, 34.50), (31.50, 34.50),
                  (31.35, 34.48), (31.22, 34.40)]
MAX_BORDER_KM  = 50.0   # beyond this, border score = 0
WEIGHT_ALERTS  = 0.5
WEIGHT_BORDER  = 0.5

def _dist_to_segment(lat, lon, p1, p2):
    cos_lat = math.cos(math.radians((lat + p1[0] + p2[0]) / 3))
    x  = (lon  - p1[1]) * 111.0 * cos_lat
    y  = (lat  - p1[0]) * 111.0
    dx = (p2[1] - p1[1]) * 111.0 * cos_lat
    dy = (p2[0] - p1[0]) * 111.0
    seg2 = dx*dx + dy*dy
    if seg2 < 1e-10:
        return math.sqrt(x*x + y*y)
    t = max(0.0, min(1.0, (x*dx + y*dy) / seg2))
    return math.sqrt((x - t*dx)**2 + (y - t*dy)**2)

def dist_to_polyline(lat, lon, poly):
    return min(_dist_to_segment(lat, lon, poly[i], poly[i+1])
               for i in range(len(poly)-1))

def border_score(lat, lon):
    d = min(dist_to_polyline(lat, lon, LEBANON_BORDER),
            dist_to_polyline(lat, lon, GAZA_BORDER))
    return max(0.0, 1.0 - d / MAX_BORDER_KM)

# ── 1. Load residential centroids ─────────────────────────────────────────────
geo_db = json.load(open(GEO_FILE))
cities = [(float(v['lat']), float(v['lon']), v['alerts'], city)
          for city, v in geo_db.items()
          if v.get('lat') and v['alerts'] >= CITY_MIN_ALERTS]
print(f"Residential reference points: {len(cities)}")

def nearest_city(lat, lon):
    return min(((dist_km((lat,lon),(c[0],c[1])), c[3]) for c in cities), key=lambda x: x[0])

# ── 2. Build route→nodes from OSM cache ──────────────────────────────────────
print("Loading OSM road nodes (1967 Israel only)...")
all_segs = pickle.load(open(OSM_CACHE, 'rb'))
segs = [s for s in all_segs if filter_segment(s)]
print(f"  {len(all_segs)} segments → {len(segs)} within 1967 borders")
route_nodes = defaultdict(list)
for seg in segs:
    name = seg.get('name','')
    if not name: continue
    lanes = seg.get('lanes')
    cap_w = {1:1.0,2:1.5,3:2.0,4:2.5}.get(lanes,1.5) if lanes else 1.5
    for pt in seg.get('geom',[]):
        if in_1967_israel(pt[0], pt[1]):
            route_nodes[name].append((pt[0], pt[1], cap_w))

for name in route_nodes:
    seen, deduped = set(), []
    for lat, lon, cw in route_nodes[name]:
        k = (round(lat,5), round(lon,5))
        if k not in seen:
            seen.add(k)
            deduped.append((lat, lon, cw))
    route_nodes[name] = deduped
print(f"  {len(route_nodes)} routes, "
      f"{sum(len(v) for v in route_nodes.values()):,} nodes")

# ── 3. Load & dedup priority shelters ────────────────────────────────────────
raw, final_max = pickle.load(open(CKPT, 'rb'))
print(f"\nLoaded {len(raw)} raw shelters (max travel time {final_max:.2f} min)")

priority_sorted = sorted(raw, key=lambda p: (p[3], p[2]), reverse=True)
base = []
for pt in priority_sorted:
    if not any(dist_km(pt[:2], k[:2]) < MIN_DEDUP_KM for k in base):
        base.append(pt)
print(f"After {MIN_DEDUP_KM} km dedup: {len(base)} shelters")

# ── 4. Urban relocation ───────────────────────────────────────────────────────
print(f"Relocating shelters within {URBAN_RADIUS_KM} km of a city...")
rural_kept, relocated, kept_urban = [], [], []

for pt in base:
    lat, lon, risk, cw, rname = pt
    d_city, cname = nearest_city(lat, lon)

    if d_city >= URBAN_RADIUS_KM:
        rural_kept.append(pt)
        continue

    # Try to find a rural node on the same road
    candidates = []
    for nlat, nlon, ncw in route_nodes.get(rname, []):
        nd, _ = nearest_city(nlat, nlon)
        if nd < URBAN_RADIUS_KM: continue
        move = dist_km((lat,lon),(nlat,nlon))
        if move < MIN_MOVE_KM: continue
        candidates.append((move, nlat, nlon, ncw))

    if not candidates:
        kept_urban.append(pt)
        continue

    candidates.sort()
    _, nlat, nlon, ncw = candidates[0]
    new_pt = (nlat, nlon, risk, max(cw, ncw), rname)
    relocated.append((pt, new_pt, cname, candidates[0][0]))

print(f"  Rural (unchanged):      {len(rural_kept):4d}")
print(f"  Relocated:              {len(relocated):4d}")
print(f"  Kept urban (no alt):    {len(kept_urban):4d}")

# ── 5. Re-dedup after relocation ──────────────────────────────────────────────
pool = rural_kept + [n for _,n,_,_ in relocated] + kept_urban
pool_sorted = sorted(pool, key=lambda p: (p[3], p[2]), reverse=True)
final = []
for pt in pool_sorted:
    if not any(dist_km(pt[:2], k[:2]) < MIN_DEDUP_KM for k in final):
        final.append(pt)

relocated_set = {(round(n[0],4), round(n[1],4)) for _,n,_,_ in relocated}
urban_set     = {(round(p[0],4), round(p[1],4)) for p in kept_urban}

print(f"\nFinal shelter count: {len(final)}  (input: {len(base)})")

# ── 6. Alert scoring ──────────────────────────────────────────────────────────
print(f"Loading Mar–Apr 2026 alerts...")
coords_map = {city: (float(v['lat']), float(v['lon']))
              for city, v in geo_db.items() if v.get('lat')}
city_counts = {}
with open(ALERTS_CSV, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('alertDate','')[:7] not in TARGET_MONTHS:
            continue
        for area in row.get('data','').split(','):
            base_name = area.strip()
            if ' - ' in base_name:
                base_name = base_name.split(' - ')[0].strip()
            if base_name:
                city_counts[base_name] = city_counts.get(base_name, 0) + 1

alert_locs = [(coords_map[c][0], coords_map[c][1], cnt, c)
              for c, cnt in city_counts.items() if c in coords_map]
covered = sum(cnt for c,cnt in city_counts.items() if c in coords_map)
total   = sum(city_counts.values())
print(f"  Coverage: {covered:,}/{total:,} ({100*covered/total:.1f}%)")

print(f"Scoring {len(final)} shelters...")
pre_scored = []
for lat, lon, risk, cw, rname in final:
    nearby = sum(cnt for clat,clon,cnt,_ in alert_locs
                 if dist_km((lat,lon),(clat,clon)) <= RADIUS_KM)
    bscore = border_score(lat, lon)
    pre_scored.append((lat, lon, risk, cw, rname, nearby, bscore))

max_alerts = max(x[5] for x in pre_scored) if pre_scored else 1

scored = []
for lat, lon, risk, cw, rname, nearby, bscore in pre_scored:
    alert_norm = nearby / max_alerts
    composite  = WEIGHT_ALERTS * alert_norm + WEIGHT_BORDER * bscore
    scored.append((lat, lon, risk, cw, rname, nearby, bscore, composite))
scored.sort(key=lambda x: x[7], reverse=True)

max_composite = scored[0][7] if scored else 1

print(f"\nTop 20 by composite score (alerts {WEIGHT_ALERTS:.0%} + border proximity {WEIGHT_BORDER:.0%}):")
print(f"  {'#':>4}  {'Zone':8}  {'Road':>12}  {'Alerts':>8}  {'Border':>6}  {'Composite':>9}  Location")
for rank, (lat, lon, risk, cw, rname, alerts, bscore, comp) in enumerate(scored[:20], 1):
    zone = is_priority_zone(lat, lon) or 'std'
    print(f"  {rank:4d}  {zone:8}  {rname:>12}  {alerts:8,}  {bscore:6.3f}  {comp:9.4f}  ({lat:.4f},{lon:.4f})")

# ── 7. Zone summary ───────────────────────────────────────────────────────────
n_north = sum(1 for lat,lon,*_ in final if lat > 33.05)
n_gaza  = sum(1 for lat,lon,*_ in final if lat < 31.60 and lon < 34.90)
n_std   = len(final) - n_north - n_gaza
print(f"\nShelters by zone: north={n_north}, gaza={n_gaza}, standard={n_std}")

# ── 8. Colour helpers (based on composite score) ──────────────────────────────
def comp_color(s):
    if s >= max_composite*.7:  return '#D63031'
    if s >= max_composite*.4:  return '#E17055'
    if s >= max_composite*.2:  return '#F9CA24'
    if s >= max_composite*.05: return '#00B894'
    return '#B2BEC3'

def comp_radius(s):
    return max(4, min(11, int(s/max(max_composite,1e-9)*10)+3))

# ── 9. Build map ──────────────────────────────────────────────────────────────
print("\nGenerating map...")
m = folium.Map(location=[31.8, 35.0], zoom_start=8, tiles="CartoDB positron")


# Relocated markers
reloc_group = folium.FeatureGroup(name="מיגוניות שהועברו מאזור מגורים", show=True)
for lat,lon,risk,cw,rname,alerts,bscore,comp in scored:
    if (round(lat,4), round(lon,4)) in relocated_set:
        folium.CircleMarker(location=[lat,lon], radius=10,
            color='#A29BFE', fill=False, weight=2,
            tooltip="הועבר מאזור מגורים").add_to(reloc_group)
reloc_group.add_to(m)

# Main shelter cluster
cluster = MarkerCluster(
    name=f"מיגוניות סופי ({len(scored)})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12}
).add_to(m)

for rank, (lat, lon, risk, cw, rname, alerts, bscore, comp) in enumerate(scored, 1):
    key4 = (round(lat,4), round(lon,4))
    zone = is_priority_zone(lat, lon)
    zone_he = {'north': 'צפון', 'gaza': 'עוטף עזה'}.get(zone, 'רגיל')
    tag = ""
    if key4 in relocated_set: tag = "<br><i style='color:#6C5CE7'>הועבר מאזור מגורים</i>"
    if key4 in urban_set:     tag = "<br><i style='color:#FDCB6E'>נותר — כביש עירוני</i>"

    folium.CircleMarker(
        location=[lat,lon],
        radius=comp_radius(comp),
        color='white', fill=True,
        fill_color=comp_color(comp),
        fill_opacity=0.92, weight=1.2,
        popup=folium.Popup(
            f"<div dir='rtl' style='font-family:Arial;font-size:13px;'>"
            f"<b>מיגונית #{rank}</b><br>"
            f"כביש: {rname} | אזור: {zone_he}<br>"
            f"ציון מורכב: <b>{comp:.3f}</b><br>"
            f"התרעות מר-אפר 2026 ({RADIUS_KM:.0f} ק\"מ): {alerts:,}<br>"
            f"קרבה לגבול (0-1): {bscore:.3f}"
            f"{tag}</div>", max_width=260),
        tooltip=f"#{rank} | {rname} | {zone_he} | ציון: {comp:.3f}",
    ).add_to(cluster)

# Legend
legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;line-height:1.8;">
  <b style="font-size:13px;">מיגוניות — ציון מורכב</b>
  <hr style="margin:6px 0">
  <b>50% התרעות (מר-אפר 2026) + 50% קרבה לגבול</b><br>
  גבולות: לבנון (צפון) | עזה (דרום-מערב)<br>
  טווח גבול: עד {MAX_BORDER_KM:.0f} ק"מ
  <hr style="margin:6px 0">
  <b>צבע = ציון מורכב:</b><br>
  <span style="color:#D63031">&#9679;</span> גבוה מאוד ({sum(1 for *_,c in scored if c>=max_composite*.7)})<br>
  <span style="color:#E17055">&#9679;</span> גבוה ({sum(1 for *_,c in scored if max_composite*.4<=c<max_composite*.7)})<br>
  <span style="color:#F9CA24">&#9679;</span> בינוני ({sum(1 for *_,c in scored if max_composite*.2<=c<max_composite*.4)})<br>
  <span style="color:#00B894">&#9679;</span> נמוך ({sum(1 for *_,c in scored if max_composite*.05<=c<max_composite*.2)})<br>
  <span style="color:#B2BEC3">&#9679;</span> מינימלי ({sum(1 for *_,c in scored if c<max_composite*.05)})
  <hr style="margin:6px 0">
  <span style="color:#A29BFE">&#9711;</span> הועבר מאזור מגורים ({len(relocated)})<br>
  סה"כ: {len(scored)} מיגוניות | תקן: 5.0 דק' (ירושלים: 3.0 דק')
  <br><span style="font-size:10px;color:#888">צפון={n_north} | עזה={n_gaza} | רגיל={n_std}</span>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
out_html = HERE / "shelters_priority_final.html"
m.save(str(out_html))
print(f"Saved: {out_html.name}")

# ── 10. Export CSV ────────────────────────────────────────────────────────────
orig_lookup = {(round(n[0],4),round(n[1],4)): (o[0],o[1],cname,km)
               for o,n,cname,km in relocated}

out_csv = HERE / "shelters_priority_final.csv"
with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=[
        'rank', 'lat', 'lon', 'road', 'zone',
        'composite_score', 'alert_score_norm', 'border_proximity_score',
        'nearby_alerts_marapr2026', 'road_risk', 'lanes_weight',
        'status', 'relocated_from_lat', 'relocated_from_lon',
        'nearest_city_when_relocated', 'moved_km'
    ])
    w.writeheader()
    for rank, (lat, lon, risk, cw, rname, alerts, bscore, comp) in enumerate(scored, 1):
        key4 = (round(lat,4), round(lon,4))
        zone = is_priority_zone(lat, lon) or 'standard'
        if key4 in relocated_set:
            status = 'relocated'
            olat, olon, cname, km = orig_lookup.get(key4, ('','','',0))
        elif key4 in urban_set:
            status = 'urban_kept'
            olat, olon, cname, km = '', '', '', 0
        else:
            status = 'rural'
            olat, olon, cname, km = '', '', '', 0
        w.writerow({
            'rank':                          rank,
            'lat':                           round(lat,5),
            'lon':                           round(lon,5),
            'road':                          rname,
            'zone':                          zone,
            'composite_score':               round(comp, 4),
            'alert_score_norm':              round(alerts / max_alerts, 4),
            'border_proximity_score':        round(bscore, 4),
            'nearby_alerts_marapr2026':      alerts,
            'road_risk':                     round(risk,2),
            'lanes_weight':                  round(cw,1),
            'status':                        status,
            'relocated_from_lat':            round(olat,5) if olat else '',
            'relocated_from_lon':            round(olon,5) if olon else '',
            'nearest_city_when_relocated':   cname,
            'moved_km':                      round(km,2) if km else '',
        })
print(f"Saved: {out_csv.name}")

print(f"\n{'─'*55}")
print(f"  Raw placements:              {len(raw):4d}")
print(f"  After {MIN_DEDUP_KM} km dedup:           {len(base):4d}")
print(f"  Relocated from urban:        {len(relocated):4d}")
print(f"  Kept urban (no alt):         {len(kept_urban):4d}")
print(f"  Final (after re-dedup):      {len(final):4d}")
print(f"    North border (5.0 min):    {n_north:4d}")
print(f"    Gaza envelope (5.0 min):   {n_gaza:4d}")
print(f"    Standard (5.0 min):        {n_std:4d}")
