"""
Fetch verified Israeli road data from OpenStreetMap via Overpass API,
then compute shelter placement and produce:
  road_shelters_osm_overlay.jpg  — shelters on the Israeli Roads.jpg background
  road_shelters_osm_schematic.jpg — dark schematic map
  road_shelters_osm.html          — interactive Folium map

Geographic scope: sovereign Israel within pre-1967 Green Line only.
(Excludes West Bank, Golan Heights, Gaza Strip)
"""
import json, time, math, pickle
import numpy as np
import requests
from collections import defaultdict
from bidi.algorithm import get_display
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

np.random.seed(7)

REPORT  = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report"
CACHE   = f"{REPORT}/osm_roads_cache.pkl"
BG_IMG  = f"{REPORT}/Israeli Roads.jpg"
OUT_OV  = f"{REPORT}/road_shelters_osm_overlay.jpg"
OUT_SC  = f"{REPORT}/road_shelters_osm_schematic.jpg"
OUT_HTML= f"{REPORT}/road_shelters_osm.html"

def H(t): return get_display(str(t))

# ══════════════════════════════════════════════════════════════════════════════
# 1.  FETCH ROADS FROM OVERPASS API
#     bbox: sovereign Israel — west=34.2, east=35.67, south=29.4, north=33.08
# ══════════════════════════════════════════════════════════════════════════════
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

def make_query(hw_filter, s, n):
    return f"""[out:json][timeout:60];
(way["highway"~"^({hw_filter})$"]({s},34.2,{n},35.67););
out geom;"""

def try_query(query, label=""):
    for url in OVERPASS_MIRRORS:
        try:
            print(f"    [{label}] {url.split('/')[2]} …", end=" ", flush=True)
            r = requests.post(url, data={"data": query}, timeout=65)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                print(f"{len(data.get('elements',[]))} ways")
                return data
            print(f"HTTP {r.status_code}")
        except Exception as e:
            print(f"err: {e}")
        time.sleep(1)
    return {"elements": []}

def fetch_roads():
    try:
        cached = pickle.load(open(CACHE, 'rb'))
        print(f"Loaded {len(cached)} roads from cache.")
        return cached
    except FileNotFoundError:
        pass

    all_elements = []
    queries = [
        ("motorway|trunk", 29.4, 33.08, "mwy+trunk"),
        ("primary", 29.4, 31.2,  "primary-S"),
        ("primary", 31.2, 32.3,  "primary-C"),
        ("primary", 32.3, 33.08, "primary-N"),
    ]
    for hw, s, n, label in queries:
        print(f"Fetching {label} …")
        d = try_query(make_query(hw, s, n), label)
        all_elements += d.get("elements", [])
        time.sleep(8)

    print(f"Total elements fetched: {len(all_elements)}")
    roads = []
    for el in all_elements:
        if el["type"] != "way" or "geometry" not in el:
            continue
        tags = el.get("tags", {})
        hw   = tags.get("highway", "")
        ref  = tags.get("ref", "")
        name = tags.get("name", "") or ref or hw
        geom = [(pt["lat"], pt["lon"]) for pt in el["geometry"]]
        if len(geom) < 2:
            continue
        roads.append({"name": name, "ref": ref, "highway": hw, "geom": geom})

    pickle.dump(roads, open(CACHE, 'wb'))
    print(f"  Cached {len(roads)} roads.")
    return roads

raw_roads = fetch_roads()

# ══════════════════════════════════════════════════════════════════════════════
# 2.  GEOGRAPHIC FILTER — sovereign Israel (pre-1967 Green Line)
# ══════════════════════════════════════════════════════════════════════════════
def _pip(lat, lon, poly):
    """Ray-casting point-in-polygon (poly is list of (lat,lon) tuples)."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

# Approximate West Bank (Judea & Samaria) polygon — Green Line boundary.
# Western edge follows the Green Line carefully through the Bethlehem/Hebron area.
# Near Jerusalem (lat 31.78) the Green Line bends east to ~lon 35.17, then returns
# west south of Jerusalem.
WEST_BANK = [
    (32.47, 35.02),   # NW near Jenin
    (32.55, 35.53),   # NE near Jordan Valley (Bet Shean / Jordan River)
    (32.00, 35.55),   # E Jordan Valley mid
    (31.78, 35.54),   # E Dead Sea north
    (31.50, 35.54),   # E Dead Sea mid
    (31.22, 35.46),   # E Dead Sea south
    (31.10, 35.12),   # SE near Arad
    (31.10, 34.90),   # S
    (31.38, 34.93),   # W near south Hebron
    (31.55, 34.97),   # W south of Bethlehem / Etzion Bloc entrance
    (31.60, 34.97),   # W Gush Etzion area
    (31.70, 35.00),   # W south of Jerusalem / Etzion Bloc western edge
    (31.75, 35.00),   # W keep boundary flat — Etzion roads excluded up to here
    (31.78, 35.17),   # W Jerusalem — Green Line bends sharply east for the city
    (31.88, 35.00),   # W Latrun / Modi'in
    (32.00, 34.96),   # W near Qalqilya
    (32.20, 34.97),   # W near Tulkarm
    (32.47, 35.02),   # close polygon
]

def in_sovereign_israel(geom):
    """True if road centroid is within pre-1967 sovereign Israel."""
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)

    # 1. Lebanon border — diagonal from Rosh HaNikra (33.07, 35.10) to Metula (33.27, 35.65)
    #    The "Finger of Galilee" reaches lat 33.27; a flat cutoff at 33.07 is wrong.
    if mlon <= 35.10:
        if mlat > 33.07:
            return False
    elif mlon <= 35.65:
        leb_lat = 33.07 + (mlon - 35.10) / (35.65 - 35.10) * (33.27 - 33.07)
        if mlat > leb_lat:
            return False
    # (east of 35.65 is Golan, caught below)

    # 2. Golan Heights (captured 1967 from Syria)
    if mlat > 32.55 and mlon > 35.67:
        return False

    # 3. Gaza Strip
    if 31.20 <= mlat <= 31.62 and 34.20 <= mlon <= 34.55:
        return False

    # 4. West Bank (Judea & Samaria) — Green Line polygon
    if _pip(mlat, mlon, WEST_BANK):
        return False

    # 5. Jordan: east of Jordan River / Dead Sea / Arava
    #    Jordan River runs ~lon 35.53–35.58 for lat 31–32.7; use 35.53 as cutoff
    #    so the West Bank Jordan Valley and Dead Sea eastern shore are excluded.
    if 31.0 <= mlat <= 32.7 and mlon > 35.53:
        return False

    # 6. Jordan: Arava valley — border line from (31.0, 35.47) to (29.50, 34.97)
    if mlat < 31.0:
        border_lon_e = 34.97 + (mlat - 29.50) / (31.0 - 29.50) * (35.47 - 34.97)
        if mlon > border_lon_e:
            return False

    # 7. South of Eilat / Taba (lat < 29.50) — definitely not Israel
    if mlat < 29.50:
        return False

    # 8. Egypt / Sinai
    #    Two-part boundary check (all geometry points, not just centroid):
    #    a) lat 31.08–31.28 (Rafah gap): border follows Mediterranean coast lon ≈ 34.27
    #    b) lat 29.50–31.08 (Sinai diagonal): straight line Rafah→Taba
    if mlat < 31.28:
        for pt_lat, pt_lon in geom:
            if 31.08 <= pt_lat < 31.28:
                if pt_lon < 34.27:          # west of Rafah meridian → Sinai
                    return False
            elif pt_lat >= 29.50:
                elim_lon = 34.27 + (31.08 - pt_lat) / (31.08 - 29.50) * (34.90 - 34.27)
                if pt_lon < elim_lon:
                    return False

    return True

# ══════════════════════════════════════════════════════════════════════════════
# 3.  ASSIGN RISK LEVEL
# ══════════════════════════════════════════════════════════════════════════════
def assign_risk(geom, highway):
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)
    max_lat = max(lats)
    # Lebanon border area: lat > 32.90
    if max_lat > 32.90:
        return 4.0
    # Gaza envelope: lat < 31.7 AND lon < 34.65
    if mlat < 31.7 and mlon < 34.65:
        return 4.0
    # Jordan Valley / Dead Sea corridor: lon > 35.38
    if mlon > 35.38:
        return 2.5
    # Deep south (Negev / Arava): lat < 30.8
    if mlat < 30.8:
        return 2.0
    if highway == "motorway":
        return 1.5
    if highway == "trunk":
        return 1.8
    return 2.0

# ══════════════════════════════════════════════════════════════════════════════
# 4.  CHAIN CONNECTED WAY SEGMENTS BY ROUTE REF
#     Groups all OSM fragments of the same numbered road into continuous
#     polylines, so interpolation happens once per road (not per 2 km stub).
# ══════════════════════════════════════════════════════════════════════════════
def build_chains(ways):
    """
    Chain a list of OSM way dicts (each with 'geom') into connected polylines.
    Returns a list of geometry lists (each geometry = list of (lat,lon)).
    """
    SNAP = 4   # round to 4 dp ≈ 11 m — matches OSM shared nodes
    snap = lambda pt: (round(pt[0], SNAP), round(pt[1], SNAP))

    adj = defaultdict(list)
    for i, w in enumerate(ways):
        adj[snap(w['geom'][0])].append((i, True))    # way i starts at this node
        adj[snap(w['geom'][-1])].append((i, False))  # way i ends at this node

    used = [False] * len(ways)
    chains = []

    for seed in range(len(ways)):
        if used[seed]:
            continue
        used[seed] = True
        chain = list(ways[seed]['geom'])

        # Grow forward from chain tail
        while True:
            ep = snap(chain[-1])
            grew = False
            for idx, at_start in adj.get(ep, []):
                if not used[idx]:
                    used[idx] = True
                    g = ways[idx]['geom']
                    chain += (list(g)[1:] if at_start else list(reversed(g))[1:])
                    grew = True
                    break
            if not grew:
                break

        # Grow backward from chain head
        while True:
            sp = snap(chain[0])
            grew = False
            for idx, at_start in adj.get(sp, []):
                if not used[idx]:
                    used[idx] = True
                    g = ways[idx]['geom']
                    prepend = list(reversed(g))[:-1] if at_start else list(g)[:-1]
                    chain = prepend + chain
                    grew = True
                    break
            if not grew:
                break

        chains.append(chain)

    return chains

# Filter, group by ref, chain, assign risk
SKIP_HW = {"motorway_link", "trunk_link", "primary_link"}

ref_groups = defaultdict(list)
skipped = 0
for rd in raw_roads:
    if rd['highway'] in SKIP_HW:
        skipped += 1
        continue
    if not in_sovereign_israel(rd['geom']):
        skipped += 1
        continue
    key = rd['ref'].split(';')[0].strip() if rd['ref'] else None
    if key:
        ref_groups[key].append(rd)
    # Unnamed connectors (no ref) are skipped — they're interchange stubs

print(f"Skipped {skipped} ways (links / outside Green Line). "
      f"Named routes: {len(ref_groups)} refs covering "
      f"{sum(len(v) for v in ref_groups.values())} way segments.")

merged = []
for key, ways in ref_groups.items():
    chains = build_chains(ways)
    # Use max risk across constituent ways (most exposed section sets the standard)
    max_risk = max(assign_risk(w['geom'], w['highway']) for w in ways)
    hw = ways[0]['highway']
    for chain_geom in chains:
        # Per-chain risk (respects local geography if chain is long)
        local_risk = assign_risk(chain_geom, hw)
        merged.append({
            'name': key,
            'highway': hw,
            'geom': chain_geom,
            'risk': local_risk,
        })

print(f"Chained into {len(merged)} road polylines.")

# ══════════════════════════════════════════════════════════════════════════════
# 5.  SHELTER PLACEMENT  (5-minute standard on all roads)
# ══════════════════════════════════════════════════════════════════════════════
def seg_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

def road_length_km(wpts):
    return sum(seg_km(wpts[i], wpts[i+1]) for i in range(len(wpts)-1))

def interpolate_km(wpts, spacing_km):
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total < spacing_km * 0.4:
        return []          # stub too short — skip
    dists = list(np.arange(0, total, spacing_km)) + [total]
    pts = []
    for tgt in sorted(set(dists)):
        seg = min(np.searchsorted(cum, tgt, side='right')-1, len(wpts)-2)
        sl = cum[seg+1]-cum[seg]
        t  = 0 if sl == 0 else (tgt-cum[seg])/sl
        pts.append((wpts[seg][0]+t*(wpts[seg+1][0]-wpts[seg][0]),
                    wpts[seg][1]+t*(wpts[seg+1][1]-wpts[seg][1])))
    return pts

def speed_kmh(risk):
    if risk >= 4.0: return 70
    if risk >= 3.0: return 80
    if risk >= 2.0: return 90
    return 110

def max_gap(risk):
    return 2 * (5/60) * speed_kmh(risk)   # 5-min standard

shelter_points = []   # (lat, lon, risk)
total_km = 0.0
for rd in merged:
    wpts = rd['geom']
    risk = rd['risk']
    km   = road_length_km(wpts)
    total_km += km
    for lat, lon in interpolate_km(wpts, max_gap(risk)):
        jlat = lat + np.random.uniform(-0.0004, 0.0004)
        jlon = lon + np.random.uniform(-0.0006, 0.0006)
        shelter_points.append((jlat, jlon, risk))

# Dedup: remove shelters within min_km of any already-placed shelter.
# 10 km minimum ensures no two shelters are needlessly close (e.g. at road junctions).
def dedup(pts, min_km=10.0):
    kept = []
    for lat, lon, risk in pts:
        if not any(seg_km((lat, lon), (kl, kn)) < min_km for kl, kn, _ in kept):
            kept.append((lat, lon, risk))
    return kept

shelter_points = dedup(shelter_points)
total = len(shelter_points)
print(f"Shelters: {total}  |  Network: {total_km:.0f} km")

# ══════════════════════════════════════════════════════════════════════════════
# 6.  COLOUR HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#F9CA24'
    return '#6AB04C'

# ══════════════════════════════════════════════════════════════════════════════
# 7.  OVERLAY MAP  (on Israeli Roads.jpg background)
# ══════════════════════════════════════════════════════════════════════════════
bg   = Image.open(BG_IMG).convert('RGB')
W, H_px = bg.size

LON_MIN, LON_MAX = 34.00, 36.00
LAT_MAX, LAT_MIN = 33.35, 29.45
MAP_TOP_PX, MAP_BOT_PX = 8, 490

def ll_to_px(lat, lon):
    fx = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    fy = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN)
    return fx * W, MAP_TOP_PX + fy * (MAP_BOT_PX - MAP_TOP_PX)

DPI = 300
fig, ax = plt.subplots(figsize=(W/DPI*6, H_px/DPI*6), dpi=DPI)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax.axis('off')
ax.imshow(np.array(bg), extent=[0, W, H_px, 0], aspect='auto', zorder=1)
ax.set_xlim(0, W); ax.set_ylim(H_px, 0)

# Road lines
for rd in merged:
    pxs = [ll_to_px(lat, lon) for lat, lon in rd['geom']]
    xs  = [p[0] for p in pxs]
    ys  = [p[1] for p in pxs]
    lw  = 1.0 if rd['risk'] >= 3.5 else 0.6
    ax.plot(xs, ys, color=rc(rd['risk']), lw=lw, alpha=0.45,
            solid_capstyle='round', zorder=2)

# Shelter markers
for tier, col, ms in [
    (lambda r: r >= 3.5, '#D63031', 70),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 55),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 42),
    (lambda r: r < 1.8, '#6AB04C', 32),
]:
    pts = [ll_to_px(lat, lon) for lat, lon, risk in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col, edgecolors='white',
                   linewidths=0.5, zorder=5, alpha=0.90)

ax.legend(handles=[
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#D63031',
                  markersize=5, label=H('גבול / עוטף  (70 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#E17055',
                  markersize=5, label=H('סיכון גבוה  (80 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#F9CA24',
                  markersize=5, label=H('כביש ראשי  (90 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#6AB04C',
                  markersize=5, label=H('כביש מהיר  (110 קמ"ש)')),
], loc='lower right', fontsize=5.5, framealpha=0.88, facecolor='white',
   edgecolor='#aaa', labelcolor='#111',
   title=H(f'מיגוניות: {total}  |  OSM  |  5 דקות'),
   title_fontsize=5.8)

plt.savefig(OUT_OV, dpi=DPI, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 95})
print(f"Overlay saved: {OUT_OV}")
plt.close()

# ══════════════════════════════════════════════════════════════════════════════
# 8.  SCHEMATIC MAP  (dark background)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(13, 19))
fig.patch.set_facecolor('#1E272E')
ax.set_facecolor('#1E272E')

for lat in np.arange(29.5, 33.5, 0.5):
    ax.axhline(lat, color='#2D3436', lw=0.4, zorder=1)
for lon in np.arange(34.2, 35.8, 0.5):
    ax.axvline(lon, color='#2D3436', lw=0.4, zorder=1)

ax.text(34.38, 31.85, H('ים תיכון'), fontsize=11, color='#4A6FA5',
        ha='center', va='center', style='italic',
        fontfamily='Arial Hebrew', alpha=0.7)
ax.text(35.50, 31.42, H('ים המלח'), fontsize=8, color='#4A6FA5',
        ha='center', va='center', style='italic',
        fontfamily='Arial Hebrew', alpha=0.6)

for rd in merged:
    lats = [p[0] for p in rd['geom']]
    lons = [p[1] for p in rd['geom']]
    risk = rd['risk']
    lw   = 2.5 if risk >= 3.5 else (2.0 if risk >= 2.5 else 1.5)
    ax.plot(lons, lats, color='white', lw=lw+2.0, alpha=0.08,
            solid_capstyle='round', zorder=3)
    ax.plot(lons, lats, color=rc(risk), lw=lw, alpha=0.85,
            solid_capstyle='round', zorder=4)

for tier, col, ms in [
    (lambda r: r >= 3.5, '#D63031', 50),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 40),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 30),
    (lambda r: r < 1.8, '#6AB04C', 24),
]:
    pts = [(lon, lat) for lat, lon, risk in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col, edgecolors='#1E272E',
                   linewidths=0.6, zorder=6, alpha=0.95)

CITIES = [
    (32.082,34.781,"תל אביב",'right',8.5,True),
    (31.782,35.216,"ירושלים",'left', 8.5,True),
    (32.820,34.981,"חיפה",   'left', 8,  False),
    (31.252,34.791,"באר שבע",'right',8,  False),
    (29.558,34.948,"אילת",   'right',8,  False),
    (33.070,35.569,"קרית שמונה",'left',7.5,False),
    (32.793,35.531,"טבריה",  'left', 7.5,False),
    (32.330,34.860,"נתניה",  'right',7.5,False),
    (31.800,34.650,"אשדוד",  'right',7.5,False),
    (31.674,34.571,"אשקלון", 'right',7.5,False),
    (32.925,35.083,"עכו",    'left', 7.5,False),
    (30.605,34.803,"מצפה רמון",'right',7,False),
]
for lat, lon, name, ha, fs, bold in CITIES:
    ax.scatter([lon],[lat], s=55, color='white', edgecolors='#636E72',
               linewidths=1.2, zorder=8)
    ax.text(lon+(-0.05 if ha=='right' else 0.05), lat,
            H(name), fontsize=fs, fontweight='bold' if bold else 'normal',
            color='#DFE6E9', fontfamily='Arial Hebrew',
            ha=ha, va='center', zorder=9)

for lon, lat, lbl in [(35.55,33.05,'לבנון'),(34.35,29.50,'מצרים'),(35.68,31.50,'ירדן')]:
    ax.text(lon, lat, H(lbl), fontsize=7.5, color='#B2BEC3',
            fontfamily='Arial Hebrew', style='italic',
            ha='right' if lon>35 else 'left')

ax.legend(handles=[
    mlines.Line2D([],[],color='#D63031',lw=3,   label=H('גבול / עוטף עזה (70 קמ"ש)')),
    mlines.Line2D([],[],color='#E17055',lw=2.5, label=H('סיכון גבוה (80 קמ"ש)')),
    mlines.Line2D([],[],color='#F9CA24',lw=2,   label=H('כביש ראשי (90 קמ"ש)')),
    mlines.Line2D([],[],color='#6AB04C',lw=2,   label=H('כביש מהיר (110 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#DFE6E9',
                  markersize=7, label=H(f'מיגונית (סה"כ {total})')),
], loc='lower left', fontsize=8.5, framealpha=0.85,
   facecolor='#2D3436', edgecolor='#636E72', labelcolor='#DFE6E9',
   title=H('תקן: 5 דקות | נתוני OSM מאומתים'),
   title_fontsize=9).get_title().set_color('#DFE6E9')

ax.set_title(H(f'מיגוניות בכבישי ישראל — {total} יחידות | OSM | תקן 5 דקות'),
             fontsize=13, fontweight='bold', color='#DFE6E9',
             fontfamily='Arial Hebrew', pad=14)
ax.set_xlim(34.18, 35.72); ax.set_ylim(29.35, 33.15)
ax.set_xlabel(H('קו אורך'), fontsize=8, color='#636E72')
ax.set_ylabel(H('קו רוחב'), fontsize=8, color='#636E72')
ax.tick_params(colors='#636E72', labelsize=7)

plt.tight_layout(pad=1.2)
plt.savefig(OUT_SC, dpi=200, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 94})
print(f"Schematic saved: {OUT_SC}")
plt.close()

# ══════════════════════════════════════════════════════════════════════════════
# 9.  INTERACTIVE HTML MAP
# ══════════════════════════════════════════════════════════════════════════════
import folium
from folium.plugins import MarkerCluster

m = folium.Map(location=[31.5, 34.9], zoom_start=8, tiles="CartoDB positron")

for rd in merged:
    folium.PolyLine(locations=rd['geom'], color=rc(rd['risk']),
                    weight=2.5, opacity=0.7,
                    tooltip=rd['name']).add_to(m)

cluster = MarkerCluster(name=f"מיגוניות ({total})",
    options={"maxClusterRadius":35,"disableClusteringAtZoom":12}).add_to(m)
for lat, lon, risk in shelter_points:
    spd = speed_kmh(risk)
    folium.CircleMarker(
        location=[lat, lon], radius=5,
        color='white', fill=True, fill_color=rc(risk),
        fill_opacity=0.9, weight=1.2,
        popup=folium.Popup(
            f"<div dir='rtl'>מיגונית<br>סיכון: {risk}<br>{spd} קמ\"ש</div>",
            max_width=180),
    ).add_to(cluster)

legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 18px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;">
  <b>מיגוניות — OSM | תקן 5 דקות | ישראל בלבד</b><hr style="margin:6px 0">
  <span style="color:#D63031">●</span> גבול / עוטף עזה (70 קמ"ש)<br>
  <span style="color:#E17055">●</span> סיכון גבוה (80 קמ"ש)<br>
  <span style="color:#F9CA24">●</span> כביש ראשי (90 קמ"ש)<br>
  <span style="color:#6AB04C">●</span> כביש מהיר (110 קמ"ש)<hr style="margin:6px 0">
  <b>סה"כ: {total} מיגוניות</b>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
m.save(OUT_HTML)
print(f"HTML map saved: {OUT_HTML}")

# ══════════════════════════════════════════════════════════════════════════════
# 10. SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
by_risk = {}
for _, _, r in shelter_points:
    by_risk[r] = by_risk.get(r, 0) + 1

print("\n── Shelter count by risk tier ──")
for r in sorted(by_risk.keys(), reverse=True):
    spd = speed_kmh(r)
    gap = max_gap(r)
    print(f"  risk {r}  ({spd} km/h, gap {gap:.1f} km):  {by_risk[r]:4d} shelters")
print(f"  TOTAL: {total}")
print(f"  Network covered: {total_km:.0f} km")

def unit_cost(r):
    if r >= 4.0: return 520_000
    if r >= 3.0: return 460_000
    if r >= 2.0: return 430_000
    return 400_000

cap = sum(unit_cost(r) for _,_,r in shelter_points)
print(f"\n── Budget estimate (excl. VAT) ──")
print(f"  Capital:           {cap/1e6:.1f}M NIS")
print(f"  + 15% contingency: {cap*1.15/1e6:.1f}M NIS")
print(f"  Annual maintenance:{total*15000/1e6:.2f}M NIS/yr")
