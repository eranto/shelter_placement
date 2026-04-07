"""
Road shelter placement — Gonzalez Farthest-First (k-center) algorithm.

Fetches Israeli road geometry from the Overpass API (cached locally),
builds a road-network graph, and places the minimum number of shelters
so that every road point is within the time limit of a shelter.

Jerusalem is held to a stricter 3-minute standard; junction/interchange
nodes get a scoring bonus so shelters land at road crossings when possible.

Outputs (written next to this script):
  shelters_overlay.jpg      — markers on the Israeli Roads background image
  shelters_schematic.jpg    — dark-theme vector schematic
  shelters.html             — interactive Folium map (GitHub Pages ready)
  osm_roads_cache.pkl       — cached Overpass response (auto-created)

Usage:
  pip install -r requirements.txt
  python optimize_shelters.py
"""

import json, time, math, pickle, heapq, os
from pathlib import Path
from collections import defaultdict

import numpy as np
import requests
from bidi.algorithm import get_display
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

np.random.seed(7)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent
CACHE    = BASE / "osm_roads_cache.pkl"
BG_IMG   = BASE / "Israeli Roads.jpg"
OUT_OV   = BASE / "shelters_overlay.jpg"
OUT_SC   = BASE / "shelters_schematic.jpg"
OUT_HTML = BASE / "index.html"

def H(t):
    """Right-to-left text shaping for Hebrew labels in matplotlib."""
    return get_display(str(t))

# ──────────────────────────────────────────────────────────────────────────────
# 1.  FETCH / LOAD ROADS  (Overpass API, cached after first run)
# ──────────────────────────────────────────────────────────────────────────────
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
            print(f"    [{label}] {url.split('/')[2]} ...", end=" ", flush=True)
            r = requests.post(url, data={"data": query}, timeout=65)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                print(f"{len(data.get('elements', []))} ways")
                return data
            print(f"HTTP {r.status_code}")
        except Exception as e:
            print(f"err: {e}")
        time.sleep(1)
    return {"elements": []}

def fetch_roads():
    if CACHE.exists():
        cached = pickle.load(open(CACHE, 'rb'))
        print(f"Loaded {len(cached)} roads from cache.")
        return cached

    all_elements = []
    queries = [
        ("motorway|trunk", 29.4, 33.08, "mwy+trunk"),
        ("primary",        29.4, 31.2,  "primary-S"),
        ("primary",        31.2, 32.3,  "primary-C"),
        ("primary",        32.3, 33.08, "primary-N"),
    ]
    for hw, s, n, label in queries:
        print(f"Fetching {label} ...")
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

# ──────────────────────────────────────────────────────────────────────────────
# 2.  GEOGRAPHIC FILTER  (pre-1967 sovereign Israel only)
# ──────────────────────────────────────────────────────────────────────────────
def _pip(lat, lon, poly):
    """Ray-casting point-in-polygon test."""
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

# Green Line (West Bank boundary) — approximate polygon
WEST_BANK = [
    (32.47, 35.02), (32.55, 35.53), (32.00, 35.55), (31.78, 35.54),
    (31.50, 35.54), (31.22, 35.46), (31.10, 35.12), (31.10, 34.90),
    (31.38, 34.93), (31.55, 34.97), (31.60, 34.97), (31.70, 35.00),
    (31.75, 35.00), (31.78, 35.17), (31.88, 35.00), (32.00, 34.96),
    (32.20, 34.97), (32.47, 35.02),
]

def in_sovereign_israel(geom):
    """Return True if road centroid lies within pre-1967 sovereign Israel."""
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)

    # Lebanon — diagonal border from Rosh HaNikra to Metula (preserves Galilee Finger)
    if mlon <= 35.10:
        if mlat > 33.07:
            return False
    elif mlon <= 35.65:
        leb_lat = 33.07 + (mlon - 35.10) / (35.65 - 35.10) * (33.27 - 33.07)
        if mlat > leb_lat:
            return False

    # Golan Heights (occupied, not sovereign Israel for this analysis)
    if mlat > 32.55 and mlon > 35.67:
        return False

    # Gaza Strip
    if 31.20 <= mlat <= 31.62 and 34.20 <= mlon <= 34.55:
        return False

    # West Bank (Green Line polygon)
    if _pip(mlat, mlon, WEST_BANK):
        return False

    # Jordan River / Dead Sea
    if 31.0 <= mlat <= 32.7 and mlon > 35.53:
        return False

    # Arava valley eastern border
    if mlat < 31.0:
        border_lon_e = 34.97 + (mlat - 29.50) / (31.0 - 29.50) * (35.47 - 34.97)
        if mlon > border_lon_e:
            return False

    if mlat < 29.50:
        return False

    # Egypt / Sinai — two-part boundary
    if mlat < 31.28:
        for pt_lat, pt_lon in geom:
            if 31.08 <= pt_lat < 31.28:
                if pt_lon < 34.27:
                    return False
            elif pt_lat >= 29.50:
                elim_lon = 34.27 + (31.08 - pt_lat) / (31.08 - 29.50) * (34.90 - 34.27)
                if pt_lon < elim_lon:
                    return False

    return True

# ──────────────────────────────────────────────────────────────────────────────
# 3.  RISK ASSIGNMENT
# ──────────────────────────────────────────────────────────────────────────────
def assign_risk(geom, highway):
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)
    if max(lats) > 32.90:      return 4.0   # North / Lebanon border
    if mlat < 31.7 and mlon < 34.65: return 4.0   # Gaza envelope
    if mlon > 35.38:           return 2.5   # Jordan Valley approach
    if mlat < 30.8:            return 2.0   # Negev
    if highway == "motorway":  return 1.5
    if highway == "trunk":     return 1.8
    return 2.0

# ──────────────────────────────────────────────────────────────────────────────
# 4.  CHAIN CONNECTED SEGMENTS
# ──────────────────────────────────────────────────────────────────────────────
def build_chains(ways):
    SNAP = 4
    snap = lambda pt: (round(pt[0], SNAP), round(pt[1], SNAP))

    adj = defaultdict(list)
    for i, w in enumerate(ways):
        adj[snap(w['geom'][0])].append((i, True))
        adj[snap(w['geom'][-1])].append((i, False))

    used   = [False] * len(ways)
    chains = []

    for seed in range(len(ways)):
        if used[seed]:
            continue
        used[seed] = True
        chain = list(ways[seed]['geom'])

        # Grow forward
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

        # Grow backward
        while True:
            sp = snap(chain[0])
            grew = False
            for idx, at_start in adj.get(sp, []):
                if not used[idx]:
                    used[idx] = True
                    g = ways[idx]['geom']
                    chain = (list(reversed(g))[:-1] if at_start else list(g)[:-1]) + chain
                    grew = True
                    break
            if not grew:
                break

        chains.append(chain)
    return chains

# ──────────────────────────────────────────────────────────────────────────────
# 5.  GEOMETRY HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def seg_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat**2 + dlon**2)

def road_length_km(wpts):
    return sum(seg_km(wpts[i], wpts[i+1]) for i in range(len(wpts) - 1))

def interpolate_km(wpts, step_km):
    cum = [0.0]
    for i in range(len(wpts) - 1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total < step_km * 0.4:
        return []
    dists = list(np.arange(0, total, step_km)) + [total]
    pts = []
    for tgt in sorted(set(dists)):
        seg = min(np.searchsorted(cum, tgt, side='right') - 1, len(wpts) - 2)
        sl  = cum[seg+1] - cum[seg]
        t   = 0 if sl == 0 else (tgt - cum[seg]) / sl
        pts.append((
            wpts[seg][0] + t * (wpts[seg+1][0] - wpts[seg][0]),
            wpts[seg][1] + t * (wpts[seg+1][1] - wpts[seg][1]),
        ))
    return pts

def speed_kmh(risk):
    if risk >= 4.0: return 70
    if risk >= 3.0: return 80
    if risk >= 2.0: return 90
    return 110

def max_gap(risk):
    return 2 * (5 / 60) * speed_kmh(risk)   # km, 5-min standard

def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#F9CA24'
    return '#6AB04C'

# ──────────────────────────────────────────────────────────────────────────────
# 6.  LOAD, FILTER AND CHAIN ROADS
# ──────────────────────────────────────────────────────────────────────────────
raw_roads = fetch_roads()

SKIP_HW   = {"motorway_link", "trunk_link", "primary_link"}
ref_groups = defaultdict(list)
skipped    = 0

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

print(f"Skipped {skipped} ways (links / outside Green Line). "
      f"Named routes: {len(ref_groups)} refs covering "
      f"{sum(len(v) for v in ref_groups.values())} way segments.")

merged = []
for key, ways in ref_groups.items():
    chains = build_chains(ways)
    hw = ways[0]['highway']
    for chain_geom in chains:
        merged.append({
            'name':    key,
            'highway': hw,
            'geom':    chain_geom,
            'risk':    assign_risk(chain_geom, hw),
        })

print(f"Chained into {len(merged)} road polylines.")
total_km = sum(road_length_km(rd['geom']) for rd in merged)
print(f"Total network: {total_km:.0f} km")

# ──────────────────────────────────────────────────────────────────────────────
# 7.  BUILD ROAD NETWORK GRAPH
# ──────────────────────────────────────────────────────────────────────────────
STEP_KM     = 0.5    # demand node every 500 m
JUNCTION_KM = 0.1    # cross-road edges within 100 m
CELL_DEG    = 0.005  # spatial grid cell ≈ 500 m

print("\nBuilding road network graph ...")

nodes          = []   # [lat, lon, risk, road_name]
road_node_seqs = []

for rd in merged:
    pts = interpolate_km(rd['geom'], STEP_KM)
    seq = []
    for lat, lon in pts:
        nodes.append([lat, lon, rd['risk'], rd['name']])
        seq.append(len(nodes) - 1)
    road_node_seqs.append(seq)

# Deduplicate shared endpoints (chain A end == chain B start)
pos_to_id  = {}
node_remap = {}
new_nodes  = []
for nid, nd in enumerate(nodes):
    key = (round(nd[0], 4), round(nd[1], 4))
    if key in pos_to_id:
        node_remap[nid] = pos_to_id[key]
    else:
        new_id = len(new_nodes)
        pos_to_id[key] = new_id
        node_remap[nid] = new_id
        new_nodes.append(nd)

road_node_seqs = [[node_remap[nid] for nid in seq] for seq in road_node_seqs]
nodes = new_nodes
N     = len(nodes)
print(f"  {len(node_remap)} raw → {N} unique demand nodes (step={STEP_KM} km)")

# Adjacency list: adj[nid] = [(neighbor_id, travel_time_minutes), ...]
adj = defaultdict(list)

for seq in road_node_seqs:
    for i in range(len(seq) - 1):
        a, b   = seq[i], seq[i+1]
        d_km   = seg_km((nodes[a][0], nodes[a][1]), (nodes[b][0], nodes[b][1]))
        tt     = d_km / speed_kmh(nodes[a][2]) * 60.0
        adj[a].append((b, tt))
        adj[b].append((a, tt))

# Zero-cost junction edges between nearby nodes on different roads
print("  Building spatial index for junction connections ...")
grid      = defaultdict(list)
node_road = {}
for rid, seq in enumerate(road_node_seqs):
    for nid in seq:
        node_road[nid] = rid

for nid, (lat, lon, risk, name) in enumerate(nodes):
    grid[(int(lat / CELL_DEG), int(lon / CELL_DEG))].append(nid)

junction_edges = 0
for nid, (lat, lon, risk, name) in enumerate(nodes):
    cr, cc = int(lat / CELL_DEG), int(lon / CELL_DEG)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for other in grid.get((cr+dr, cc+dc), []):
                if other <= nid or node_road.get(nid) == node_road.get(other):
                    continue
                if seg_km((lat, lon), (nodes[other][0], nodes[other][1])) <= JUNCTION_KM:
                    adj[nid].append((other, 0.0))
                    adj[other].append((nid, 0.0))
                    junction_edges += 1

print(f"  {junction_edges} junction edges added")
print(f"  Graph: {N} nodes, {sum(len(v) for v in adj.values()) // 2} edges")

# Junction nodes — at least one zero-cost cross-road edge
junction_node_set = set()
for nid in range(N):
    for (other, w) in adj[nid]:
        if w == 0.0 and node_road.get(nid) != node_road.get(other):
            junction_node_set.add(nid)
            break
print(f"  {len(junction_node_set)} junction/interchange nodes")

# Jerusalem priority zone (west of Green Line, ~lon 35.17)
JER_LAT = (31.72, 31.87)
JER_LON = (34.92, 35.18)
jerusalem_nodes = frozenset(
    nid for nid in range(N)
    if JER_LAT[0] <= nodes[nid][0] <= JER_LAT[1]
    and JER_LON[0] <= nodes[nid][1] <= JER_LON[1]
)
print(f"  {len(jerusalem_nodes)} nodes in Jerusalem priority zone")

# ──────────────────────────────────────────────────────────────────────────────
# 8.  GONZALEZ FARTHEST-FIRST (k-center) ALGORITHM
#
#   Reference: Gonzalez, T.F. (1985). Clustering to minimize the maximum
#   intercluster distance. Theoretical Computer Science, 38, 293–306.
#   Greedy 2-approximation for the k-center problem on metric spaces.
# ──────────────────────────────────────────────────────────────────────────────
TIME_LIMIT     = 5.0   # minutes — standard everywhere
JER_TIME_LIMIT = 3.0   # minutes — Jerusalem (stricter)
JUNCTION_BONUS = 0.30  # preference score bonus for junction nodes

def dijkstra_from(source):
    dist = [math.inf] * N
    dist[source] = 0.0
    heap = [(0.0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist

def node_time_limit(nid):
    return JER_TIME_LIMIT if nid in jerusalem_nodes else TIME_LIMIT

def node_score(nid):
    return dist_to_nearest[nid] / node_time_limit(nid) + \
           (JUNCTION_BONUS if nid in junction_node_set else 0.0)

def all_covered():
    return all(dist_to_nearest[nid] <= node_time_limit(nid) for nid in range(N))

print(f"\nRunning Gonzalez k-center "
      f"(standard={TIME_LIMIT} min, Jerusalem={JER_TIME_LIMIT} min) ...")

dist_to_nearest  = [math.inf] * N
shelter_node_ids = []
iteration        = 0

while True:
    if iteration == 0:
        chosen = max(range(N), key=lambda i: nodes[i][2])   # highest-risk first
    else:
        if all_covered():
            break
        chosen = max(range(N), key=node_score)

    shelter_node_ids.append(chosen)
    iteration += 1

    d_from = dijkstra_from(chosen)
    for i in range(N):
        if d_from[i] < dist_to_nearest[i]:
            dist_to_nearest[i] = d_from[i]

    lat_c, lon_c = nodes[chosen][0], nodes[chosen][1]
    print(f"  #{iteration:3d}  ({lat_c:.4f}, {lon_c:.4f})  "
          f"risk={nodes[chosen][2]:.1f}  "
          f"{'[JER]' if chosen in jerusalem_nodes else '     '}  "
          f"{'[JCT]' if chosen in junction_node_set else '     '}  "
          f"worst_uncovered={max(dist_to_nearest):.2f} min")

final_max = max(dist_to_nearest)
print(f"\nDone: {len(shelter_node_ids)} shelters, "
      f"max travel time = {final_max:.2f} min")

shelter_points = [
    (nodes[nid][0], nodes[nid][1], nodes[nid][2])
    for nid in shelter_node_ids
]

# Post-placement dedup: remove shelters within 2.5 km straight-line of an earlier one
def _post_dedup(pts, min_km=2.5):
    kept = []
    for lat, lon, risk in pts:
        if not any(seg_km((lat, lon), (kl, kn)) < min_km for kl, kn, _ in kept):
            kept.append((lat, lon, risk))
    return kept

before         = len(shelter_points)
shelter_points = _post_dedup(shelter_points, min_km=2.5)
total          = len(shelter_points)
print(f"Post-dedup: {before} → {total} shelters (removed {before - total} within 2.5 km)")

# ──────────────────────────────────────────────────────────────────────────────
# 9.  OVERLAY MAP  (markers on background image)
# ──────────────────────────────────────────────────────────────────────────────
if BG_IMG.exists():
    print("\nGenerating overlay map ...")
    bg      = Image.open(BG_IMG).convert('RGB')
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

    for rd in merged:
        pxs = [ll_to_px(lat, lon) for lat, lon in rd['geom']]
        ax.plot([p[0] for p in pxs], [p[1] for p in pxs],
                color=rc(rd['risk']), lw=0.7, alpha=0.45, zorder=2)

    for tier, col, ms in [
        (lambda r: r >= 3.5,       '#D63031', 70),
        (lambda r: 2.5 <= r < 3.5, '#E17055', 55),
        (lambda r: 1.8 <= r < 2.5, '#F9CA24', 42),
        (lambda r: r < 1.8,        '#6AB04C', 32),
    ]:
        pts = [ll_to_px(lat, lon) for lat, lon, risk in shelter_points if tier(risk)]
        if pts:
            xs, ys = zip(*pts)
            ax.scatter(xs, ys, s=ms, color=col, edgecolors='white',
                       linewidths=0.5, zorder=5, alpha=0.90)

    ax.legend(handles=[
        mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#D63031',
                      markersize=5, label=H('גבול / עוטף  (70 קמ"ש)')),
        mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#E17055',
                      markersize=5, label=H('סיכון גבוה  (80 קמ"ש)')),
        mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#F9CA24',
                      markersize=5, label=H('כביש ראשי  (90 קמ"ש)')),
        mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#6AB04C',
                      markersize=5, label=H('כביש מהיר  (110 קמ"ש)')),
    ], loc='lower right', fontsize=5.5, framealpha=0.88, facecolor='white',
       edgecolor='#aaa', labelcolor='#111',
       title=H(f'מיגוניות: {total}  |  5 דקות'),
       title_fontsize=5.8)

    plt.savefig(OUT_OV, dpi=DPI, format='jpeg', bbox_inches='tight',
                pil_kwargs={'quality': 95})
    print(f"Overlay saved: {OUT_OV}")
    plt.close()
else:
    print(f"Note: '{BG_IMG.name}' not found — skipping overlay map.")

# ──────────────────────────────────────────────────────────────────────────────
# 10. SCHEMATIC MAP
# ──────────────────────────────────────────────────────────────────────────────
print("Generating schematic map ...")
fig, ax = plt.subplots(figsize=(13, 19))
fig.patch.set_facecolor('#1E272E')
ax.set_facecolor('#1E272E')

for lat in np.arange(29.5, 33.5, 0.5):
    ax.axhline(lat, color='#2D3436', lw=0.4, zorder=1)
for lon in np.arange(34.2, 35.8, 0.5):
    ax.axvline(lon, color='#2D3436', lw=0.4, zorder=1)

for rd in merged:
    lats = [p[0] for p in rd['geom']]
    lons = [p[1] for p in rd['geom']]
    risk = rd['risk']
    lw   = 2.5 if risk >= 3.5 else (2.0 if risk >= 2.5 else 1.5)
    ax.plot(lons, lats, color='white', lw=lw+2.0, alpha=0.08, zorder=3)
    ax.plot(lons, lats, color=rc(risk), lw=lw, alpha=0.85, zorder=4)

for tier, col, ms in [
    (lambda r: r >= 3.5,       '#D63031', 50),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 40),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 30),
    (lambda r: r < 1.8,        '#6AB04C', 24),
]:
    pts = [(lon, lat) for lat, lon, risk in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col, edgecolors='#1E272E',
                   linewidths=0.6, zorder=6, alpha=0.95)

CITIES = [
    (32.082, 34.781, 'תל אביב',   'right', 8.5, True),
    (31.782, 35.216, 'ירושלים',   'left',  8.5, True),
    (32.820, 34.981, 'חיפה',      'left',  8,   False),
    (31.252, 34.791, 'באר שבע',   'right', 8,   False),
    (29.558, 34.948, 'אילת',      'right', 8,   False),
    (33.070, 35.569, 'קרית שמונה','left',  7.5, False),
    (32.793, 35.531, 'טבריה',     'left',  7.5, False),
    (32.330, 34.860, 'נתניה',     'right', 7.5, False),
    (31.800, 34.650, 'אשדוד',     'right', 7.5, False),
    (31.674, 34.571, 'אשקלון',    'right', 7.5, False),
    (30.605, 34.803, 'מצפה רמון', 'right', 7,   False),
]
for lat, lon, name, ha, fs, bold in CITIES:
    ax.scatter([lon], [lat], s=55, color='white', edgecolors='#636E72',
               linewidths=1.2, zorder=8)
    ax.text(lon + (-0.05 if ha == 'right' else 0.05), lat, H(name),
            fontsize=fs, fontweight='bold' if bold else 'normal',
            color='#DFE6E9', fontfamily='Arial Hebrew',
            ha=ha, va='center', zorder=9)

for lon, lat, lbl in [(35.55, 33.05, 'לבנון'), (34.35, 29.50, 'מצרים'), (35.68, 31.50, 'ירדן')]:
    ax.text(lon, lat, H(lbl), fontsize=7.5, color='#B2BEC3',
            fontfamily='Arial Hebrew', style='italic',
            ha='right' if lon > 35 else 'left')

ax.legend(handles=[
    mlines.Line2D([], [], color='#D63031', lw=3,   label=H('גבול / עוטף (70 קמ"ש)')),
    mlines.Line2D([], [], color='#E17055', lw=2.5, label=H('סיכון גבוה (80 קמ"ש)')),
    mlines.Line2D([], [], color='#F9CA24', lw=2,   label=H('כביש ראשי (90 קמ"ש)')),
    mlines.Line2D([], [], color='#6AB04C', lw=2,   label=H('כביש מהיר (110 קמ"ש)')),
    mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#DFE6E9',
                  markersize=7, label=H(f'מיגונית (סה"כ {total})')),
], loc='lower left', fontsize=8.5, framealpha=0.85,
   facecolor='#2D3436', edgecolor='#636E72', labelcolor='#DFE6E9',
   title=H('תקן: 5 דקות | Gonzalez k-center'),
   title_fontsize=9).get_title().set_color('#DFE6E9')

ax.set_title(H(f'מיגוניות בכבישי ישראל — {total} יחידות | תקן 5 דקות'),
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

# ──────────────────────────────────────────────────────────────────────────────
# 11. INTERACTIVE HTML MAP  (written to index.html for GitHub Pages)
# ──────────────────────────────────────────────────────────────────────────────
print("Generating interactive HTML map ...")
import folium
from folium.plugins import MarkerCluster

m = folium.Map(location=[31.5, 34.9], zoom_start=8, tiles="CartoDB positron")

for rd in merged:
    folium.PolyLine(locations=rd['geom'], color=rc(rd['risk']),
                    weight=2.5, opacity=0.7,
                    tooltip=rd['name']).add_to(m)

cluster = MarkerCluster(
    name=f"מיגוניות ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
).add_to(m)

for lat, lon, risk in shelter_points:
    folium.CircleMarker(
        location=[lat, lon], radius=5,
        color='white', fill=True, fill_color=rc(risk),
        fill_opacity=0.9, weight=1.2,
        popup=folium.Popup(
            f"<div dir='rtl'>מיגונית<br>סיכון: {risk}<br>{speed_kmh(risk)} קמ\"ש</div>",
            max_width=180),
    ).add_to(cluster)

legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 18px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;">
  <b>מיגוניות — Gonzalez k-center | תקן 5 דקות</b>
  <hr style="margin:6px 0">
  <span style="color:#D63031">&#9679;</span> גבול / עוטף עזה (70 קמ"ש)<br>
  <span style="color:#E17055">&#9679;</span> סיכון גבוה (80 קמ"ש)<br>
  <span style="color:#F9CA24">&#9679;</span> כביש ראשי (90 קמ"ש)<br>
  <span style="color:#6AB04C">&#9679;</span> כביש מהיר (110 קמ"ש)
  <hr style="margin:6px 0">
  <b>סה"כ: {total} מיגוניות | ישראל בלבד</b>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
m.save(str(OUT_HTML))
print(f"HTML map saved: {OUT_HTML}")

# ──────────────────────────────────────────────────────────────────────────────
# 12. SUMMARY
# ──────────────────────────────────────────────────────────────────────────────
by_risk = {}
for _, _, r in shelter_points:
    by_risk[r] = by_risk.get(r, 0) + 1

def unit_cost(r):
    if r >= 4.0: return 520_000
    if r >= 3.0: return 460_000
    if r >= 2.0: return 430_000
    return 400_000

cap = sum(unit_cost(r) for _, _, r in shelter_points)

print("\n" + "=" * 60)
print("SHELTER PLACEMENT SUMMARY")
print("=" * 60)
print(f"  Algorithm         : Gonzalez Farthest-First (k-center)")
print(f"  Network           : {total_km:.0f} km")
print(f"  Total shelters    : {total}")
print(f"  Max travel time   : {final_max:.2f} min  (target: {TIME_LIMIT} min)")
print(f"  Graph nodes       : {N}")
print(f"  Junction edges    : {junction_edges}")
print()
print("  Shelters by risk tier:")
for r in sorted(by_risk.keys(), reverse=True):
    print(f"    risk {r}  ({speed_kmh(r)} km/h, gap {max_gap(r):.1f} km):  {by_risk[r]:4d}")
print(f"  TOTAL: {total}")
print()
print("  Budget estimate (excl. VAT):")
print(f"    Capital:            {cap/1e6:.1f}M NIS")
print(f"    + 15% contingency:  {cap*1.15/1e6:.1f}M NIS")
print(f"    Annual maintenance: {total*15_000/1e6:.2f}M NIS/yr")
print("=" * 60)
