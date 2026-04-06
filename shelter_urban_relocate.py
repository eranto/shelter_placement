"""
Relocate road shelters that sit inside urban areas to the nearest rural
point on the same road outside the urban zone.

Logic:
  - "Urban area" = within URBAN_RADIUS_KM of a significant city centroid
    (cities with >= CITY_MIN_ALERTS alerts as population proxy)
  - For each urban-proximate shelter, scan all nodes of the same road route
    for the nearest node that lies outside any urban zone, is at least
    MIN_DIST_FROM_SHELTER_KM away (so we actually move it), and passes
    the global 2.5-km dedup constraint.
  - If no such node exists the shelter is kept (whole road is urban).

Outputs:
  shelters_rural_alert_ranked.html         — interactive map
  shelters_rural_marapr2026_ranked.html    — Mar–Apr 2026 version
  shelters_rural_deduped.csv               — final shelter list with relocation flag
"""

import csv, json, math, pickle
from pathlib import Path
from collections import defaultdict
import folium
from folium.plugins import MarkerCluster

HERE       = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")
CKPT       = HERE / "shelter_points_traffic.pkl"
OSM_CACHE  = HERE / "osm_roads_traffic_cache.pkl"
GEO_FILE   = "/tmp/geocoded_cities.json"
ALERTS_CSV = "/tmp/israel_alerts.csv"

RADIUS_KM          = 15.0   # alert catchment radius
MIN_DEDUP_KM       = 2.5    # min distance between any two kept shelters
URBAN_RADIUS_KM    = 2.5    # shelter inside this distance from a city → candidate for relocation
CITY_MIN_ALERTS    = 400    # alert count threshold to count as a significant residential area
MIN_MOVE_KM        = 1.0    # minimum relocation distance (don't jitter, actually move)
TARGET_MONTHS_ALL  = None   # None = all time
TARGET_MONTHS_2026 = {'2026-03', '2026-04'}

# ── Helpers ───────────────────────────────────────────────────────────────────
def dist_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

# ── 1. Load residential area centroids ───────────────────────────────────────
geo_db = json.load(open(GEO_FILE))
cities = [
    (float(v['lat']), float(v['lon']), v['alerts'], city)
    for city, v in geo_db.items()
    if v.get('lat') and v['alerts'] >= CITY_MIN_ALERTS
]
print(f"Residential reference points: {len(cities)} cities "
      f"(>= {CITY_MIN_ALERTS} alerts)")

def nearest_city_dist(lat, lon):
    """Return (distance_km, city_name) to nearest significant city."""
    if not cities:
        return 999, ''
    dists = [(dist_km((lat,lon),(clat,clon)), cname)
             for clat, clon, _, cname in cities]
    return min(dists, key=lambda x: x[0])

def is_urban(lat, lon):
    d, _ = nearest_city_dist(lat, lon)
    return d < URBAN_RADIUS_KM

# ── 2. Build route→nodes lookup from OSM segments ────────────────────────────
print("Building road-node lookup from OSM cache...")
segs = pickle.load(open(OSM_CACHE, 'rb'))

route_nodes = defaultdict(list)   # route_ref → [(lat, lon, cap_w)]
for seg in segs:
    rname = seg.get('name', '')
    if not rname:
        continue
    lanes = seg.get('lanes')
    cap_w = {1:1.0, 2:1.5, 3:2.0, 4:2.5}.get(lanes, 1.5) if lanes else 1.5
    for pt in seg.get('geom', []):
        route_nodes[rname].append((pt[0], pt[1], cap_w))

# Deduplicate nodes within each route (OSM ways share boundary nodes)
for rname in route_nodes:
    seen, deduped = set(), []
    for lat, lon, cw in route_nodes[rname]:
        key = (round(lat,5), round(lon,5))
        if key not in seen:
            seen.add(key)
            deduped.append((lat, lon, cw))
    route_nodes[rname] = deduped

total_nodes = sum(len(v) for v in route_nodes.values())
print(f"  {len(route_nodes)} routes, {total_nodes:,} unique road nodes")

# ── 3. Load and dedup base shelters ──────────────────────────────────────────
shelter_raw, _ = pickle.load(open(CKPT, 'rb'))
priority_sorted = sorted(shelter_raw, key=lambda p: (p[3], p[2]), reverse=True)
base_shelters = []
for pt in priority_sorted:
    if not any(dist_km(pt[:2], k[:2]) < MIN_DEDUP_KM for k in base_shelters):
        base_shelters.append(pt)
print(f"\nBase shelters after {MIN_DEDUP_KM} km dedup: {len(base_shelters)}")

# ── 4. Relocate urban shelters ────────────────────────────────────────────────
print(f"Relocating shelters within {URBAN_RADIUS_KM} km of a city "
      f"(>= {CITY_MIN_ALERTS} alerts)...")

relocated  = []   # (orig_pt, new_pt, city_name, move_km) — successfully moved
kept_urban = []   # pts kept despite being urban (whole road is urban)
rural_kept = []   # pts already outside urban zone

for pt in base_shelters:
    lat, lon, risk, cw, rname = pt
    d_city, cname = nearest_city_dist(lat, lon)

    if d_city >= URBAN_RADIUS_KM:
        # Already rural — keep as-is
        rural_kept.append(pt)
        continue

    # Try to find a rural replacement node on the same road
    candidates = []
    for nlat, nlon, ncw in route_nodes.get(rname, []):
        nd_city, _ = nearest_city_dist(nlat, nlon)
        if nd_city < URBAN_RADIUS_KM:
            continue                           # still urban
        move = dist_km((lat,lon),(nlat,nlon))
        if move < MIN_MOVE_KM:
            continue                           # didn't actually move
        candidates.append((move, nlat, nlon, ncw))

    if not candidates:
        # Whole road is urban or no nodes available — keep original
        kept_urban.append(pt)
        continue

    # Pick nearest rural node
    candidates.sort()
    _, nlat, nlon, ncw = candidates[0]
    new_pt = (nlat, nlon, risk, max(cw, ncw), rname)
    relocated.append((pt, new_pt, cname, candidates[0][0]))

print(f"  Already rural:     {len(rural_kept):4d}")
print(f"  Relocated:         {len(relocated):4d}")
print(f"  Kept (whole-road): {len(kept_urban):4d}")
print(f"  Relocation sample (first 10):")
for orig, new, cname, km in relocated[:10]:
    print(f"    {orig[4]:>6}  moved {km:.1f} km away from {cname}  "
          f"({orig[0]:.4f},{orig[1]:.4f}) → ({new[0]:.4f},{new[1]:.4f})")

# ── 5. Merge into final shelter list and re-dedup ────────────────────────────
candidates_pool = (
    rural_kept +
    [new for _, new, _, _ in relocated] +
    kept_urban
)

# Re-dedup after relocation (some relocated nodes may now be too close)
priority2 = sorted(candidates_pool, key=lambda p: (p[3], p[2]), reverse=True)
final_shelters = []
for pt in priority2:
    if not any(dist_km(pt[:2], k[:2]) < MIN_DEDUP_KM for k in final_shelters):
        final_shelters.append(pt)

relocated_set = {(round(n[0],4), round(n[1],4)) for _, n, _, _ in relocated}
urban_set     = {(round(p[0],4), round(p[1],4)) for p in kept_urban}

print(f"\nFinal shelter count after re-dedup: {len(final_shelters)} "
      f"(was {len(base_shelters)})")

# ── 6. Alert scoring helper ───────────────────────────────────────────────────
def build_alert_locations(target_months=None):
    """Return [(lat,lon,count,city)] from the alerts CSV + geocoded coords."""
    coords_map = {city: (float(v['lat']), float(v['lon']))
                  for city, v in geo_db.items() if v.get('lat')}
    city_counts = {}
    import csv as _csv
    with open(ALERTS_CSV, encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        for row in reader:
            ym = row.get('alertDate','')[:7]
            if target_months and ym not in target_months:
                continue
            for area in row.get('data','').split(','):
                base = area.strip()
                if ' - ' in base:
                    base = base.split(' - ')[0].strip()
                if base:
                    city_counts[base] = city_counts.get(base, 0) + 1
    locs = [(coords_map[c][0], coords_map[c][1], cnt, c)
            for c, cnt in city_counts.items() if c in coords_map]
    covered = sum(cnt for c, cnt in city_counts.items() if c in coords_map)
    total   = sum(city_counts.values())
    return locs, covered, total

def score_shelters(shelters, alert_locs):
    scored = []
    for lat, lon, risk, cw, rname in shelters:
        nearby = sum(cnt for clat,clon,cnt,_ in alert_locs
                     if dist_km((lat,lon),(clat,clon)) <= RADIUS_KM)
        scored.append((lat, lon, risk, cw, rname, nearby))
    return sorted(scored, key=lambda x: x[5], reverse=True)

# ── 7. Score: all-time and Mar–Apr 2026 ──────────────────────────────────────
print("\nScoring all-time alerts...")
locs_all, cov_all, tot_all = build_alert_locations(None)
scored_all = score_shelters(final_shelters, locs_all)
print(f"  Coverage: {cov_all:,}/{tot_all:,} ({100*cov_all/tot_all:.1f}%)")

print("Scoring Mar–Apr 2026 alerts...")
locs_2026, cov_2026, tot_2026 = build_alert_locations(TARGET_MONTHS_2026)
scored_2026 = score_shelters(final_shelters, locs_2026)
print(f"  Coverage: {cov_2026:,}/{tot_2026:,} ({100*cov_2026/tot_2026:.1f}%)")

# ── 8. Build map ──────────────────────────────────────────────────────────────
def make_map(scored, title_he, subtitle, fname):
    max_score = scored[0][5] if scored else 1

    def col(s):
        if s >= max_score*.7: return '#D63031'
        if s >= max_score*.4: return '#E17055'
        if s >= max_score*.2: return '#F9CA24'
        if s >= max_score*.05: return '#00B894'
        return '#B2BEC3'

    def rad(s):
        return max(4, min(11, int(s/max(max_score,1)*10)+3))

    m = folium.Map(location=[32.0, 35.0], zoom_start=8, tiles="CartoDB positron")

    # Highlight relocated shelters
    reloc_group = folium.FeatureGroup(name="מיגוניות שהועברו מאזור מגורים", show=True)
    for lat, lon, risk, cw, rname, alerts in scored:
        key = (round(lat,4), round(lon,4))
        if key in relocated_set:
            folium.CircleMarker(
                location=[lat,lon], radius=10,
                color='#6C5CE7', fill=False, weight=2.5,
                tooltip="הועבר מאזור מגורים",
            ).add_to(reloc_group)
    reloc_group.add_to(m)

    # Highlight urban-kept shelters
    urban_group = folium.FeatureGroup(name="מיגוניות באזור מגורים (ללא חלופה)", show=False)
    for lat, lon, risk, cw, rname, alerts in scored:
        key = (round(lat,4), round(lon,4))
        if key in urban_set:
            folium.CircleMarker(
                location=[lat,lon], radius=9,
                color='#FDCB6E', fill=False, weight=2,
                tooltip="באזור מגורים — אין חלופה כפרית על כביש זה",
            ).add_to(urban_group)
    urban_group.add_to(m)

    cluster = MarkerCluster(
        name=f"{title_he} ({len(scored)})",
        options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
    ).add_to(m)

    for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored, 1):
        key = (round(lat,4), round(lon,4))
        tag = ""
        if key in relocated_set: tag = "<br><i>הועבר מאזור מגורים</i>"
        if key in urban_set:     tag = "<br><i>נותר — כל הכביש עירוני</i>"
        folium.CircleMarker(
            location=[lat,lon], radius=rad(alerts),
            color='white', fill=True, fill_color=col(alerts),
            fill_opacity=0.92, weight=1.0,
            popup=folium.Popup(
                f"<div dir='rtl' style='font-family:Arial;font-size:13px;'>"
                f"<b>מיגונית #{rank}</b><br>"
                f"כביש: {rname}<br>"
                f"התרעות ({RADIUS_KM:.0f} ק\"מ): <b>{alerts:,}</b><br>"
                f"סיכון: {risk:.1f} | נתיבים: {cw:.1f}{tag}</div>",
                max_width=240),
            tooltip=f"#{rank} | כביש {rname} | {alerts:,} התרעות",
        ).add_to(cluster)

    legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;
     line-height:1.8;">
  <b style="font-size:13px;">{title_he}</b><br>
  <span style="font-size:11px;color:#555;">{subtitle}</span>
  <hr style="margin:6px 0">
  <span style="color:#D63031">&#9679;</span> גבוה מאוד &nbsp;
  <span style="color:#E17055">&#9679;</span> גבוה<br>
  <span style="color:#F9CA24">&#9679;</span> בינוני &nbsp;
  <span style="color:#00B894">&#9679;</span> נמוך<br>
  <span style="color:#B2BEC3">&#9679;</span> מינימלי
  <hr style="margin:6px 0">
  <span style="color:#6C5CE7">&#9711;</span> הועבר מאזור מגורים ({len(relocated)})<br>
  <span style="color:#FDCB6E">&#9711;</span> נותר — כביש עירוני ({len(kept_urban)})<br>
  <hr style="margin:6px 0">
  סה"כ: {len(scored)} מיגוניות
</div>"""
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl().add_to(m)
    out = HERE / fname
    m.save(str(out))
    print(f"  Saved: {fname}")

print("\nGenerating maps...")
make_map(scored_all,  "מיגוניות כל הזמנים — הועברו מאזורי מגורים",
         "Oct 2023 – Apr 2026", "shelters_rural_alltime_ranked.html")
make_map(scored_2026, "מיגוניות מר-אפר 2026 — הועברו מאזורי מגורים",
         "מרץ-אפריל 2026 בלבד", "shelters_rural_marapr2026_ranked.html")

# ── 9. Export CSV ─────────────────────────────────────────────────────────────
# Rank lookup from both scorings
rank_all  = {(round(lat,5),round(lon,5)): i+1
             for i,(lat,lon,*_) in enumerate(scored_all)}
rank_2026 = {(round(lat,5),round(lon,5)): i+1
             for i,(lat,lon,*_) in enumerate(scored_2026)}

orig_lookup = {
    (round(n[0],4), round(n[1],4)): (o[0],o[1],cname,km)
    for o, n, cname, km in relocated
}

with open(HERE / "shelters_rural_deduped.csv", 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=[
        'alert_rank_alltime','alert_rank_marapr2026',
        'lat','lon','road','risk_score','lanes_weight',
        'alerts_alltime_15km','alerts_marapr2026_15km',
        'status','relocated_from_lat','relocated_from_lon','nearest_city','moved_km'
    ])
    w.writeheader()
    score2026_map = {(round(lat,5),round(lon,5)): alerts
                     for lat,lon,risk,cw,rname,alerts in scored_2026}
    for lat,lon,risk,cw,rname,alerts_all in scored_all:
        key4 = (round(lat,4),round(lon,4))
        key5 = (round(lat,5),round(lon,5))
        if key4 in relocated_set:
            status = 'relocated'
            orig_lat, orig_lon, cname, km = orig_lookup.get(key4, ('','','',0))
        elif key4 in urban_set:
            status = 'urban_kept'
            orig_lat, orig_lon, cname, km = '', '', '', 0
        else:
            status = 'rural'
            orig_lat, orig_lon, cname, km = '', '', '', 0
        w.writerow({
            'alert_rank_alltime':       rank_all.get(key5,''),
            'alert_rank_marapr2026':    rank_2026.get(key5,''),
            'lat':                      round(lat,5),
            'lon':                      round(lon,5),
            'road':                     rname,
            'risk_score':               round(risk,2),
            'lanes_weight':             round(cw,1),
            'alerts_alltime_15km':      alerts_all,
            'alerts_marapr2026_15km':   score2026_map.get(key5,''),
            'status':                   status,
            'relocated_from_lat':       round(orig_lat,5) if orig_lat else '',
            'relocated_from_lon':       round(orig_lon,5) if orig_lon else '',
            'nearest_city':             cname,
            'moved_km':                 round(km,2) if km else '',
        })
print(f"  Saved: shelters_rural_deduped.csv")

# ── 10. Summary ───────────────────────────────────────────────────────────────
print(f"\n{'─'*55}")
print(f"  Input shelters (post 2.5 km dedup):  {len(base_shelters):4d}")
print(f"  Already rural:                        {len(rural_kept):4d}")
print(f"  Successfully relocated:               {len(relocated):4d}")
print(f"  Kept urban (no rural alternative):    {len(kept_urban):4d}")
print(f"  Final shelters (after re-dedup):      {len(final_shelters):4d}")
