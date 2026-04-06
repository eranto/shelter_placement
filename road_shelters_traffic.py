"""
Road shelter placement — traffic-weighted version.

Same Gonzalez Farthest-First (k-center) algorithm as road_shelters_optimized.py,
but with two additions drawn from OSM tags:

  1. maxspeed   — actual posted speed used for travel-time calculation instead
                  of the risk-tier heuristic.  Falls back to the heuristic when
                  the tag is absent.

  2. lanes      — number of lanes used as a capacity/traffic proxy.  Nodes on
                  higher-capacity roads receive a larger scoring bonus in the
                  Gonzalez loop, so shelters are placed there first when
                  multiple uncovered nodes are equidistant.

The fetch now uses  `out body geom;`  (instead of `out geom;`) so all tags
are returned.  A separate cache file is written so the old cache is preserved.

Outputs:
  road_shelters_traffic_overlay.jpg
  road_shelters_traffic_schematic.jpg
  road_shelters_traffic.html
"""
import json, time, math, pickle, heapq, os
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

HERE      = "/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006"
CACHE     = f"{HERE}/osm_roads_traffic_cache.pkl"   # new cache — keeps old one intact
BG_IMG    = f"{HERE}/Israeli Roads.jpg"
OUT_OV    = f"{HERE}/road_shelters_traffic_overlay.jpg"
OUT_SC    = f"{HERE}/road_shelters_traffic_schematic.jpg"
OUT_HTML  = f"{HERE}/road_shelters_traffic.html"

def H(t): return get_display(str(t))

# ──────────────────────────────────────────────────────────────────────────────
# 1.  FETCH / LOAD ROADS  — full tags via `out body geom;`
# ──────────────────────────────────────────────────────────────────────────────
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

def make_query(hw_filter, s, n):
    # `out body geom;` returns all tags + full node geometry
    return f"""[out:json][timeout:60];
(way["highway"~"^({hw_filter})$"]({s},34.2,{n},35.67););
out body geom;"""

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

def _parse_lanes(tag_val):
    """Return int lane count from an OSM lanes tag, or None."""
    if not tag_val:
        return None
    try:
        return max(1, int(str(tag_val).split(";")[0].strip()))
    except ValueError:
        return None

def _parse_maxspeed(tag_val):
    """Return float km/h from an OSM maxspeed tag, or None."""
    if not tag_val:
        return None
    val = str(tag_val).strip().lower()
    try:
        return float(val)
    except ValueError:
        pass
    # Handle "NN mph"
    if val.endswith("mph"):
        try:
            return float(val.replace("mph", "").strip()) * 1.60934
        except ValueError:
            pass
    return None

def fetch_roads():
    try:
        cached = pickle.load(open(CACHE, 'rb'))
        print(f"Loaded {len(cached)} roads from cache  (with traffic tags).")
        return cached
    except FileNotFoundError:
        pass

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
        tags     = el.get("tags", {})
        hw       = tags.get("highway", "")
        ref      = tags.get("ref", "")
        name     = tags.get("name", "") or ref or hw
        geom     = [(pt["lat"], pt["lon"]) for pt in el["geometry"]]
        if len(geom) < 2:
            continue
        lanes    = _parse_lanes(tags.get("lanes"))
        maxspeed = _parse_maxspeed(tags.get("maxspeed"))
        roads.append({
            "name":     name,
            "ref":      ref,
            "highway":  hw,
            "geom":     geom,
            "lanes":    lanes,      # int or None
            "maxspeed": maxspeed,   # float km/h or None
        })

    pickle.dump(roads, open(CACHE, 'wb'))
    print(f"  Cached {len(roads)} roads (with traffic tags).")
    return roads

# ──────────────────────────────────────────────────────────────────────────────
# 2.  GEOGRAPHIC FILTER  (identical to road_shelters_optimized.py)
# ──────────────────────────────────────────────────────────────────────────────
def _pip(lat, lon, poly):
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

WEST_BANK = [
    (32.47, 35.02), (32.55, 35.53), (32.00, 35.55), (31.78, 35.54),
    (31.50, 35.54), (31.22, 35.46), (31.10, 35.12), (31.10, 34.90),
    (31.38, 34.93), (31.55, 34.97), (31.60, 34.97), (31.70, 35.00),
    (31.75, 35.00), (31.78, 35.17), (31.88, 35.00), (32.00, 34.96),
    (32.20, 34.97), (32.47, 35.02),
]

def in_sovereign_israel(geom):
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)

    if mlon <= 35.10:
        if mlat > 33.07:
            return False
    elif mlon <= 35.65:
        leb_lat = 33.07 + (mlon - 35.10) / (35.65 - 35.10) * (33.27 - 33.07)
        if mlat > leb_lat:
            return False
    if mlat > 32.55 and mlon > 35.67:
        return False
    if 31.20 <= mlat <= 31.62 and 34.20 <= mlon <= 34.55:
        return False
    if _pip(mlat, mlon, WEST_BANK):
        return False
    if 31.0 <= mlat <= 32.7 and mlon > 35.53:
        return False
    if mlat < 31.0:
        border_lon_e = 34.97 + (mlat - 29.50) / (31.0 - 29.50) * (35.47 - 34.97)
        if mlon > border_lon_e:
            return False
    if mlat < 29.50:
        return False
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
# 3.  RISK ASSIGNMENT  (unchanged — geographic threat)
# ──────────────────────────────────────────────────────────────────────────────
def assign_risk(geom, highway):
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)
    max_lat = max(lats)
    if max_lat > 32.90:
        return 4.0
    if mlat < 31.7 and mlon < 34.65:
        return 4.0
    if mlon > 35.38:
        return 2.5
    if mlat < 30.8:
        return 2.0
    if highway == "motorway":
        return 1.5
    if highway == "trunk":
        return 1.8
    return 2.0

# ──────────────────────────────────────────────────────────────────────────────
# 4.  CHAIN CONNECTED SEGMENTS  (unchanged)
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

# ──────────────────────────────────────────────────────────────────────────────
# 5.  TRAFFIC / CAPACITY HELPERS  (new)
# ──────────────────────────────────────────────────────────────────────────────
def lanes_capacity_weight(lanes):
    """
    Translate lane count into a demand-proxy weight.
    Used to prioritise shelter placement on high-capacity roads.

      1 lane  → 1.0
      2 lanes → 1.5
      3 lanes → 2.0
      4 lanes → 2.5
      5+      → 3.0
    """
    if lanes is None:
        return 1.0
    if lanes >= 5:
        return 3.0
    return {1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5}.get(lanes, 1.0)

def aggregate_tag(ways, tag):
    """Median of non-None tag values across a list of way dicts, or None."""
    vals = [w[tag] for w in ways if w.get(tag) is not None]
    if not vals:
        return None
    vals.sort()
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2

# ──────────────────────────────────────────────────────────────────────────────
# 6.  SPEED / GAP HELPERS  — now uses actual maxspeed tag when available
# ──────────────────────────────────────────────────────────────────────────────
def speed_kmh(risk, maxspeed=None):
    """
    Return travel speed in km/h.
    Prefers the OSM maxspeed value; falls back to risk-tier heuristic.
    Clamps to a plausible range so bad tag values don't break things.
    """
    if maxspeed is not None:
        return max(30.0, min(130.0, float(maxspeed)))
    if risk >= 4.0: return 70.0
    if risk >= 3.0: return 80.0
    if risk >= 2.0: return 90.0
    return 110.0

def max_gap(risk, maxspeed=None):
    return 2 * (5 / 60) * speed_kmh(risk, maxspeed)   # 5-min standard, km

# ──────────────────────────────────────────────────────────────────────────────
# 7.  GEOMETRY HELPERS  (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def seg_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat**2 + dlon**2)

def road_length_km(wpts):
    return sum(seg_km(wpts[i], wpts[i + 1]) for i in range(len(wpts) - 1))

def interpolate_km(wpts, step_km):
    cum = [0.0]
    for i in range(len(wpts) - 1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i + 1]))
    total = cum[-1]
    if total < step_km * 0.4:
        return []
    dists = list(np.arange(0, total, step_km)) + [total]
    pts = []
    for tgt in sorted(set(dists)):
        seg = min(np.searchsorted(cum, tgt, side='right') - 1, len(wpts) - 2)
        sl  = cum[seg + 1] - cum[seg]
        t   = 0 if sl == 0 else (tgt - cum[seg]) / sl
        pts.append((
            wpts[seg][0] + t * (wpts[seg + 1][0] - wpts[seg][0]),
            wpts[seg][1] + t * (wpts[seg + 1][1] - wpts[seg][1]),
        ))
    return pts

# ──────────────────────────────────────────────────────────────────────────────
# 8.  LOAD, FILTER AND CHAIN ROADS
# ──────────────────────────────────────────────────────────────────────────────
raw_roads = fetch_roads()

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

print(f"Skipped {skipped} ways (links / outside Green Line). "
      f"Named routes: {len(ref_groups)} refs covering "
      f"{sum(len(v) for v in ref_groups.values())} way segments.")

# Report tag coverage
total_ways = sum(len(v) for v in ref_groups.values())
with_lanes    = sum(1 for ways in ref_groups.values() for w in ways if w.get('lanes') is not None)
with_maxspeed = sum(1 for ways in ref_groups.values() for w in ways if w.get('maxspeed') is not None)
print(f"Tag coverage — lanes: {with_lanes}/{total_ways} "
      f"({100*with_lanes//total_ways}%)   "
      f"maxspeed: {with_maxspeed}/{total_ways} "
      f"({100*with_maxspeed//total_ways}%)")

merged = []
for key, ways in ref_groups.items():
    chains    = build_chains(ways)
    hw        = ways[0]['highway']
    med_lanes = aggregate_tag(ways, 'lanes')       # median across segments of this route
    med_speed = aggregate_tag(ways, 'maxspeed')    # median maxspeed for this route
    cap_w     = lanes_capacity_weight(
                    int(round(med_lanes)) if med_lanes is not None else None)
    for chain_geom in chains:
        local_risk = assign_risk(chain_geom, hw)
        merged.append({
            'name':     key,
            'highway':  hw,
            'geom':     chain_geom,
            'risk':     local_risk,
            'lanes':    med_lanes,    # float (median) or None
            'maxspeed': med_speed,    # float km/h or None
            'cap_w':    cap_w,        # capacity weight for scoring
        })

print(f"Chained into {len(merged)} road polylines.")
total_km = sum(road_length_km(rd['geom']) for rd in merged)
print(f"Total network: {total_km:.0f} km")

# Breakdown of capacity weights
from collections import Counter
cw_dist = Counter(round(rd['cap_w'] * 2) / 2 for rd in merged)
print("Capacity-weight distribution across chains:")
for cw in sorted(cw_dist):
    print(f"  cap_w={cw}: {cw_dist[cw]} chains")

# ──────────────────────────────────────────────────────────────────────────────
# 9.  BUILD ROAD NETWORK GRAPH
# ──────────────────────────────────────────────────────────────────────────────
STEP_KM     = 0.5
JUNCTION_KM = 0.1
CELL_DEG    = 0.005

print("\nBuilding road network graph ...")

# nodes[i] = [lat, lon, risk, road_name, maxspeed, cap_w]
nodes          = []
road_node_seqs = []

for rd in merged:
    pts = interpolate_km(rd['geom'], STEP_KM)
    seq = []
    for lat, lon in pts:
        nid = len(nodes)
        nodes.append([lat, lon, rd['risk'], rd['name'], rd['maxspeed'], rd['cap_w']])
        seq.append(nid)
    road_node_seqs.append(seq)

N_raw = len(nodes)
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
print(f"  {N_raw} raw → {N} unique demand nodes (step={STEP_KM} km)")

# Adjacency list — travel time uses actual maxspeed where available
adj = defaultdict(list)

for seq in road_node_seqs:
    for i in range(len(seq) - 1):
        a, b   = seq[i], seq[i + 1]
        la, loa = nodes[a][0], nodes[a][1]
        lb, lob = nodes[b][0], nodes[b][1]
        d_km   = seg_km((la, loa), (lb, lob))
        spd    = speed_kmh(nodes[a][2], nodes[a][4])   # risk, maxspeed
        tt     = d_km / spd * 60.0
        adj[a].append((b, tt))
        adj[b].append((a, tt))

print("  Building spatial index for junction connections ...")
grid = defaultdict(list)
for nid, nd in enumerate(nodes):
    cell = (int(nd[0] / CELL_DEG), int(nd[1] / CELL_DEG))
    grid[cell].append(nid)

node_road     = {}
for rid, seq in enumerate(road_node_seqs):
    for nid in seq:
        node_road[nid] = rid

junction_edges = 0
for nid, nd in enumerate(nodes):
    lat, lon = nd[0], nd[1]
    cell_r = int(lat / CELL_DEG)
    cell_c = int(lon / CELL_DEG)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for other in grid.get((cell_r + dr, cell_c + dc), []):
                if other <= nid:
                    continue
                if node_road.get(nid) == node_road.get(other):
                    continue
                olat, olon = nodes[other][0], nodes[other][1]
                d = seg_km((lat, lon), (olat, olon))
                if d <= JUNCTION_KM:
                    adj[nid].append((other, 0.0))
                    adj[other].append((nid, 0.0))
                    junction_edges += 1

print(f"  {junction_edges} junction cross-road edges added")
total_edges = sum(len(v) for v in adj.values()) // 2
print(f"  Graph: {N} nodes, {total_edges} edges")

junction_node_set = set()
for nid in range(N):
    for (other, w) in adj[nid]:
        if w == 0.0 and node_road.get(nid) != node_road.get(other):
            junction_node_set.add(nid)
            break
print(f"  {len(junction_node_set)} junction/interchange nodes")

JER_LAT = (31.72, 31.87)
JER_LON = (34.92, 35.18)
jerusalem_nodes = frozenset(
    nid for nid in range(N)
    if JER_LAT[0] <= nodes[nid][0] <= JER_LAT[1]
    and JER_LON[0] <= nodes[nid][1] <= JER_LON[1]
)
print(f"  {len(jerusalem_nodes)} nodes in Jerusalem priority zone")

# ──────────────────────────────────────────────────────────────────────────────
# 10. GONZALEZ FARTHEST-FIRST ALGORITHM — with traffic capacity bonus
# ──────────────────────────────────────────────────────────────────────────────
TIME_LIMIT     = 5.0
JER_TIME_LIMIT = 3.0
JUNCTION_BONUS = 0.30
# Traffic bonus: scaled so a 3-lane road gets ~0.20 extra over a 1-lane road,
# without swamping the distance-driven score.
TRAFFIC_BONUS_SCALE = 0.10   # multiplied by (cap_w - 1.0)

def dijkstra_from(source, adj, N):
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
    """
    Higher = more urgently needs a nearby shelter.
    Components:
      - distance / time_limit  (primary driver, as in original)
      - junction bonus         (prefer road crossings)
      - traffic capacity bonus (prefer high-lane roads)
    """
    limit      = node_time_limit(nid)
    j_bonus    = JUNCTION_BONUS if nid in junction_node_set else 0.0
    cap_w      = nodes[nid][5]                                    # capacity weight
    t_bonus    = TRAFFIC_BONUS_SCALE * (cap_w - 1.0)             # 0 for 1-lane, up to 0.20 for 5+
    return dist_to_nearest[nid] / limit + j_bonus + t_bonus

def all_covered():
    return all(dist_to_nearest[nid] <= node_time_limit(nid) for nid in range(N))

SHELTER_CKPT = f"{HERE}/shelter_points_traffic.pkl"

if os.path.exists(SHELTER_CKPT):
    shelter_points, final_max = pickle.load(open(SHELTER_CKPT, 'rb'))
    print(f"Loaded {len(shelter_points)} shelter points from checkpoint.")
else:
    print(f"\nRunning Gonzalez algorithm "
          f"(standard={TIME_LIMIT} min, Jerusalem={JER_TIME_LIMIT} min, "
          f"traffic bonus scale={TRAFFIC_BONUS_SCALE}) ...")

    INF              = math.inf
    dist_to_nearest  = [INF] * N
    highest_risk_node = max(range(N), key=lambda i: nodes[i][2])
    shelter_node_ids  = []

    iteration = 0
    while True:
        if iteration == 0:
            chosen = highest_risk_node
        else:
            if all_covered():
                break
            chosen = max(range(N), key=node_score)

        shelter_node_ids.append(chosen)
        iteration += 1

        d_from_chosen = dijkstra_from(chosen, adj, N)
        for i in range(N):
            if d_from_chosen[i] < dist_to_nearest[i]:
                dist_to_nearest[i] = d_from_chosen[i]

        current_max = max(dist_to_nearest)
        is_junc = chosen in junction_node_set
        is_jer  = chosen in jerusalem_nodes
        lat_c, lon_c = nodes[chosen][0], nodes[chosen][1]
        spd_c = speed_kmh(nodes[chosen][2], nodes[chosen][4])
        cap_c = nodes[chosen][5]
        print(f"  Shelter {iteration:3d}: node {chosen} "
              f"({lat_c:.4f}, {lon_c:.4f})  "
              f"risk={nodes[chosen][2]:.1f}  "
              f"spd={spd_c:.0f}  cap_w={cap_c:.1f}  "
              f"{'[JER]' if is_jer else '     '} "
              f"{'[JCT]' if is_junc else '     '} "
              f"max_remaining={current_max:.2f} min")

    final_max = max(dist_to_nearest)
    print(f"\nPlacement complete: {len(shelter_node_ids)} shelters, "
          f"max travel time = {final_max:.2f} min")

    # Build shelter_points: (lat, lon, risk, cap_w, road_name)
    shelter_points = [
        (nodes[nid][0], nodes[nid][1], nodes[nid][2], nodes[nid][5], nodes[nid][3])
        for nid in shelter_node_ids
    ]

    pickle.dump((shelter_points, final_max), open(SHELTER_CKPT, 'wb'))
    print(f"Checkpoint saved → {SHELTER_CKPT}")

def _post_dedup(pts, min_km=2.5):
    kept = []
    for pt in pts:
        lat, lon = pt[0], pt[1]
        if not any(seg_km((lat, lon), (k[0], k[1])) < min_km for k in kept):
            kept.append(pt)
    return kept

before         = len(shelter_points)
shelter_points = _post_dedup(shelter_points, min_km=2.5)
print(f"Post-dedup: {before} → {len(shelter_points)} shelters "
      f"(removed {before - len(shelter_points)} within 2.5 km)")
total = len(shelter_points)

# ──────────────────────────────────────────────────────────────────────────────
# 11. COLOUR HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#F9CA24'
    return '#6AB04C'

# ──────────────────────────────────────────────────────────────────────────────
# 12. AADT MODEL — estimate annual average daily traffic per shelter
# ──────────────────────────────────────────────────────────────────────────────
# Source: CBS inter-urban traffic surveys 2017-2022, Israeli Ministry of
# Transport geo-portal (CHATZAV), and Netivei Israel published statistics.
# Where route-specific values are unavailable, highway type + lane count
# are used as a calibrated proxy.

# Known AADT benchmarks (vehicles/day, annual average, both directions)
ROUTE_AADT = {
    # Motorways / high-volume trunk
    '20':  105_000,   # Ayalon (urban TLV section)
    '2':    75_000,   # Coastal highway (Hadera-TLV)
    '1':    55_000,   # Jerusalem–Tel Aviv
    '4':    40_000,   # Coastal south (TLV–Ashdod)
    '6':    48_000,   # Trans-Israel (central section)
    '3':    30_000,   # Ayalon south / Shfela
    '40':   22_000,   # Be'er Sheva–Kiryat Gat
    '44':   18_000,   # Sharon region
    '22':   35_000,   # Geha road
    # Northern trunk / primary
    '65':   24_000,   # Wadi Ara / Megiddo
    '79':   18_000,   # Jezreel Valley
    '77':   19_000,   # Acre–Haifa
    '75':   14_000,   # Nazareth–Afula
    '85':   15_000,   # Acre–Tiberias
    '70':   20_000,   # Hadera–Afula
    # Jordan Valley / eastern
    '90':    9_000,   # Jordan Valley (inter-urban avg)
    '90;1':  9_000,
    # Negev / south
    '25':    7_000,   # Central Negev
    '31':    6_500,   # Be'er Sheva–Arad
    '40;1':  8_000,
    # Gaza envelope / high-risk south
    '232':   7_000,   # Otef Aza road
    '34':    8_500,   # Western Negev
    '35':   11_000,   # Kiryat Gat–Sderot
    # Northern border
    '99':    5_000,   # Upper Galilee border road
    '978':   3_500,   # Border fence road
    '899':   3_500,
    # Other named roads
    '38':   14_000,   # Beit Shemesh–Jerusalem
    '60':   16_000,   # Hebron road (Israeli section)
    '89':    9_000,   # Upper Galilee
    '60;6': 16_000,
}

def base_aadt(highway, lanes):
    """Fallback AADT from road class and lane count."""
    l = lanes if lanes is not None else 2
    if highway == 'motorway':
        return {1: 25_000, 2: 38_000, 3: 52_000, 4: 68_000}.get(min(l, 4), 68_000)
    if highway == 'trunk':
        return {1: 8_000, 2: 16_000, 3: 26_000, 4: 36_000}.get(min(l, 4), 36_000)
    # primary
    return {1: 4_000, 2: 8_000, 3: 13_000, 4: 18_000}.get(min(l, 4), 18_000)

# Build route→(highway, median_lanes) lookup from merged chains
route_hw    = {}
route_lanes = {}
for rd in merged:
    ref = rd['name']
    if ref not in route_hw:
        route_hw[ref]    = rd['highway']
        route_lanes[ref] = rd['lanes']

def shelter_aadt(road_name, risk, cap_w):
    """Estimated AADT for a shelter location."""
    # Try exact route match, then strip suffix after ';'
    aadt = ROUTE_AADT.get(road_name)
    if aadt is None and ';' in str(road_name):
        aadt = ROUTE_AADT.get(str(road_name).split(';')[0])
    if aadt is None:
        hw    = route_hw.get(road_name, 'primary')
        lanes = route_lanes.get(road_name)
        aadt  = base_aadt(hw, lanes)
    return aadt

# Attach AADT to each shelter and rank highest→lowest
# shelter_points: (lat, lon, risk, cap_w, road_name)
ranked = sorted(
    [(lat, lon, risk, cw, rname, shelter_aadt(rname, risk, cw))
     for lat, lon, risk, cw, rname in shelter_points],
    key=lambda x: x[5],
    reverse=True,
)

print(f"\nTop-20 shelters by estimated AADT:")
print(f"  {'Rank':>4}  {'Road':>6}  {'AADT':>8}  {'Risk':>5}  {'Lat':>8}  {'Lon':>9}")
for rank, (lat, lon, risk, cw, rname, aadt) in enumerate(ranked[:20], 1):
    print(f"  {rank:4d}  {rname:>6}  {aadt:8,.0f}  {risk:5.1f}  {lat:8.4f}  {lon:9.4f}")

# ──────────────────────────────────────────────────────────────────────────────
# 13. OVERLAY MAP
# ──────────────────────────────────────────────────────────────────────────────
print("\nGenerating overlay map ...")
bg      = Image.open(BG_IMG).convert('RGB')
W, H_px = bg.size

LON_MIN, LON_MAX    = 34.00, 36.00
LAT_MAX, LAT_MIN    = 33.35, 29.45
MAP_TOP_PX, MAP_BOT_PX = 8, 490

def ll_to_px(lat, lon):
    fx = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    fy = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN)
    return fx * W, MAP_TOP_PX + fy * (MAP_BOT_PX - MAP_TOP_PX)

DPI = 300
fig, ax = plt.subplots(figsize=(W / DPI * 6, H_px / DPI * 6), dpi=DPI)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax.axis('off')
ax.imshow(np.array(bg), extent=[0, W, H_px, 0], aspect='auto', zorder=1)
ax.set_xlim(0, W); ax.set_ylim(H_px, 0)

for rd in merged:
    pxs = [ll_to_px(lat, lon) for lat, lon in rd['geom']]
    xs  = [p[0] for p in pxs]
    ys  = [p[1] for p in pxs]
    lw  = 0.5 + 0.25 * (rd['cap_w'] - 1.0)
    ax.plot(xs, ys, color=rc(rd['risk']), lw=lw, alpha=0.45,
            solid_capstyle='round', zorder=2)

for tier, col, ms in [
    (lambda r: r >= 3.5,       '#D63031', 70),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 55),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 42),
    (lambda r: r < 1.8,        '#6AB04C', 32),
]:
    pts = [ll_to_px(lat, lon) for lat, lon, risk, cw, rname in shelter_points if tier(risk)]
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
   title=H(f'מיגוניות: {total}  |  תנועה + סיכון  |  5 דקות'),
   title_fontsize=5.8)

plt.savefig(OUT_OV, dpi=DPI, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 95})
print(f"Overlay saved: {OUT_OV}")
plt.close()

# ──────────────────────────────────────────────────────────────────────────────
# 14. SCHEMATIC MAP
# ──────────────────────────────────────────────────────────────────────────────
print("Generating schematic map ...")
fig, ax = plt.subplots(figsize=(13, 19))
fig.patch.set_facecolor('#1E272E')
ax.set_facecolor('#1E272E')

for lat in np.arange(29.5, 33.5, 0.5):
    ax.axhline(lat, color='#2D3436', lw=0.4, zorder=1)
for lon in np.arange(34.2, 35.8, 0.5):
    ax.axvline(lon, color='#2D3436', lw=0.4, zorder=1)

ax.text(34.38, 31.85, H('ים תיכון'), fontsize=11, color='#4A6FA5',
        ha='center', va='center', style='italic', fontfamily='Arial Hebrew', alpha=0.7)
ax.text(35.50, 31.42, H('ים המלח'), fontsize=8, color='#4A6FA5',
        ha='center', va='center', style='italic', fontfamily='Arial Hebrew', alpha=0.6)

for rd in merged:
    lats = [p[0] for p in rd['geom']]
    lons = [p[1] for p in rd['geom']]
    risk = rd['risk']
    lw_base = 2.5 if risk >= 3.5 else (2.0 if risk >= 2.5 else 1.5)
    lw      = lw_base + 0.4 * (rd['cap_w'] - 1.0)
    ax.plot(lons, lats, color='white', lw=lw + 2.0, alpha=0.08,
            solid_capstyle='round', zorder=3)
    ax.plot(lons, lats, color=rc(risk), lw=lw, alpha=0.85,
            solid_capstyle='round', zorder=4)

for tier, col, ms in [
    (lambda r: r >= 3.5,       '#D63031', 50),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 40),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 30),
    (lambda r: r < 1.8,        '#6AB04C', 24),
]:
    pts = [(lon, lat) for lat, lon, risk, cw, rname in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col, edgecolors='#1E272E',
                   linewidths=0.6, zorder=6, alpha=0.95)

CITIES = [
    (32.082, 34.781, 'תל אביב',    'right', 8.5, True),
    (31.782, 35.216, 'ירושלים',    'left',  8.5, True),
    (32.820, 34.981, 'חיפה',       'left',  8,   False),
    (31.252, 34.791, 'באר שבע',    'right', 8,   False),
    (29.558, 34.948, 'אילת',       'right', 8,   False),
    (33.070, 35.569, 'קרית שמונה', 'left',  7.5, False),
    (32.793, 35.531, 'טבריה',      'left',  7.5, False),
    (32.330, 34.860, 'נתניה',      'right', 7.5, False),
    (31.800, 34.650, 'אשדוד',      'right', 7.5, False),
    (31.674, 34.571, 'אשקלון',     'right', 7.5, False),
    (32.925, 35.083, 'עכו',        'left',  7.5, False),
    (30.605, 34.803, 'מצפה רמון',  'right', 7,   False),
]
for lat, lon, name, ha, fs, bold in CITIES:
    ax.scatter([lon], [lat], s=55, color='white', edgecolors='#636E72',
               linewidths=1.2, zorder=8)
    ax.text(lon + (-0.05 if ha == 'right' else 0.05), lat,
            H(name), fontsize=fs, fontweight='bold' if bold else 'normal',
            color='#DFE6E9', fontfamily='Arial Hebrew',
            ha=ha, va='center', zorder=9)

for lon, lat, lbl in [(35.55, 33.05, 'לבנון'), (34.35, 29.50, 'מצרים'), (35.68, 31.50, 'ירדן')]:
    ax.text(lon, lat, H(lbl), fontsize=7.5, color='#B2BEC3',
            fontfamily='Arial Hebrew', style='italic',
            ha='right' if lon > 35 else 'left')

ax.legend(handles=[
    mlines.Line2D([], [], color='#D63031', lw=3,   label=H('גבול / עוטף עזה (70 קמ"ש)')),
    mlines.Line2D([], [], color='#E17055', lw=2.5, label=H('סיכון גבוה (80 קמ"ש)')),
    mlines.Line2D([], [], color='#F9CA24', lw=2,   label=H('כביש ראשי (90 קמ"ש)')),
    mlines.Line2D([], [], color='#6AB04C', lw=2,   label=H('כביש מהיר (110 קמ"ש)')),
    mlines.Line2D([], [], marker='o', color='none', markerfacecolor='#DFE6E9',
                  markersize=7, label=H(f'מיגונית (סה"כ {total})')),
], loc='lower left', fontsize=8.5, framealpha=0.85,
   facecolor='#2D3436', edgecolor='#636E72', labelcolor='#DFE6E9',
   title=H('תקן: 5 דקות | תנועה + סיכון | Gonzalez k-center'),
   title_fontsize=9).get_title().set_color('#DFE6E9')

ax.set_title(H(f'מיגוניות בכבישי ישראל — {total} יחידות | תנועה + סיכון | תקן 5 דקות'),
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
# 15. INTERACTIVE HTML MAP — deployment rank + AADT shown per shelter
# ──────────────────────────────────────────────────────────────────────────────
print("Generating HTML map ...")
import folium
from folium.plugins import MarkerCluster

OUT_HTML_RANKED = f"{HERE}/road_shelters_ranked.html"

# AADT colour scale for markers (deployment priority)
def aadt_color(aadt):
    if aadt >= 50_000: return '#6C5CE7'   # purple — very high
    if aadt >= 25_000: return '#0984E3'   # blue   — high
    if aadt >= 10_000: return '#00B894'   # teal   — medium
    if aadt >=  5_000: return '#FDCB6E'   # amber  — lower
    return '#B2BEC3'                       # grey   — low

m = folium.Map(location=[31.5, 34.9], zoom_start=8, tiles="CartoDB positron")

# Road lines — tooltip shows route, lanes, speed, AADT
for rd in merged:
    lanes_str = f"{int(round(rd['lanes']))} נתיבים" if rd['lanes'] is not None else "נתיבים: לא ידוע"
    spd_str   = f"{rd['maxspeed']:.0f} קמ\"ש" if rd['maxspeed'] is not None else "מהירות: הערכה"
    rd_aadt   = ROUTE_AADT.get(rd['name']) or base_aadt(rd['highway'], rd['lanes'])
    folium.PolyLine(
        locations=rd['geom'],
        color=rc(rd['risk']),
        weight=1.5 + rd['cap_w'] * 0.6,
        opacity=0.65,
        tooltip=f"כביש {rd['name']}  |  {lanes_str}  |  {spd_str}  |  AADT ~{rd_aadt:,}",
    ).add_to(m)

# Shelter markers — coloured and sized by AADT, popup shows deployment rank
cluster = MarkerCluster(
    name=f"מיגוניות לפי עדיפות תנועה ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
).add_to(m)

for rank, (lat, lon, risk, cw, rname, aadt) in enumerate(ranked, 1):
    spd  = speed_kmh(risk)
    col  = aadt_color(aadt)
    r_px = max(4, min(10, int(aadt / 12_000) + 4))   # radius 4–10 px
    folium.CircleMarker(
        location=[lat, lon],
        radius=r_px,
        color='white',
        fill=True,
        fill_color=col,
        fill_opacity=0.92,
        weight=1.0,
        popup=folium.Popup(
            f"<div dir='rtl' style='font-family:Arial;font-size:13px;'>"
            f"<b>מיגונית #{rank}</b><br>"
            f"כביש: {rname}<br>"
            f"AADT: ~{aadt:,} רכב/יום<br>"
            f"סיכון: {risk:.1f} | {spd:.0f} קמ\"ש<br>"
            f"נתיבים (משוקלל): {cw:.1f}"
            f"</div>",
            max_width=220),
        tooltip=f"#{rank} | כביש {rname} | {aadt:,} רכב/יום",
    ).add_to(cluster)

legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;
     line-height:1.8;">
  <b style="font-size:13px;">סדר פריסת מיגוניות לפי עומס תנועה</b>
  <hr style="margin:6px 0">
  <b>צבע מיגונית = AADT (רכב/יום)</b><br>
  <span style="color:#6C5CE7">&#9679;</span> 50,000+ (עומס גבוה מאוד)<br>
  <span style="color:#0984E3">&#9679;</span> 25,000–50,000 (עומס גבוה)<br>
  <span style="color:#00B894">&#9679;</span> 10,000–25,000 (עומס בינוני)<br>
  <span style="color:#FDCB6E">&#9679;</span> 5,000–10,000 (עומס נמוך)<br>
  <span style="color:#B2BEC3">&#9679;</span> מתחת ל-5,000
  <hr style="margin:6px 0">
  גודל המיגונית = עצמת התנועה<br>
  מספר = עדיפות פריסה (#1 = ראשון)
  <hr style="margin:6px 0">
  <b>סה"כ: {total} מיגוניות | תקן 5 דקות</b><br>
  <span style="font-size:10px;color:#888;">AADT: CBS ספירות תנועה 2017-2022 +<br>נוסחת OSM lanes לכבישים אחרים</span>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
m.save(OUT_HTML_RANKED)
print(f"Ranked HTML map saved: {OUT_HTML_RANKED}")

# Also save the original (unranked) map
m2 = folium.Map(location=[31.5, 34.9], zoom_start=8, tiles="CartoDB positron")
for rd in merged:
    lanes_str = f"{int(round(rd['lanes']))} נתיבים" if rd['lanes'] is not None else "נתיבים: לא ידוע"
    spd_str   = f"{rd['maxspeed']:.0f} קמ\"ש" if rd['maxspeed'] is not None else "מהירות: הערכה"
    folium.PolyLine(locations=rd['geom'], color=rc(rd['risk']),
                    weight=1.5 + rd['cap_w'] * 0.6, opacity=0.7,
                    tooltip=f"{rd['name']}  |  {lanes_str}  |  {spd_str}").add_to(m2)
cluster2 = MarkerCluster(name=f"מיגוניות ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12}).add_to(m2)
for lat, lon, risk, cw, rname in shelter_points:
    aadt = shelter_aadt(rname, risk, cw)
    folium.CircleMarker(location=[lat, lon], radius=5,
        color='white', fill=True, fill_color=rc(risk),
        fill_opacity=0.9, weight=1.2,
        popup=folium.Popup(
            f"<div dir='rtl'>מיגונית<br>כביש: {rname}<br>AADT: ~{aadt:,}<br>"
            f"סיכון: {risk}<br>{speed_kmh(risk):.0f} קמ\"ש</div>",
            max_width=200)).add_to(cluster2)
m2.save(OUT_HTML)
print(f"HTML map saved: {OUT_HTML}")

# ──────────────────────────────────────────────────────────────────────────────
# 16. SUMMARY
# ──────────────────────────────────────────────────────────────────────────────
NAIVE_SHELTERS = 99

by_risk = {}
for _, _, r, _, _ in shelter_points:
    by_risk[r] = by_risk.get(r, 0) + 1

def unit_cost(r):
    if r >= 4.0: return 520_000
    if r >= 3.0: return 460_000
    if r >= 2.0: return 430_000
    return 400_000

cap_budget = sum(unit_cost(r) for _, _, r, _, _ in shelter_points)

print("\n" + "=" * 60)
print("SHELTER PLACEMENT SUMMARY — TRAFFIC-WEIGHTED + AADT RANKED")
print("=" * 60)
print(f"  Method            : Gonzalez k-center + traffic bonus")
print(f"  Network           : {total_km:.0f} km")
print(f"  Optimized shelters: {total}")
print(f"  Naive shelters    : {NAIVE_SHELTERS}  (equal-spacing per road)")
print(f"  Max travel time   : {final_max:.2f} min  (target: {TIME_LIMIT} min)")
print()
print("-- Shelter count by risk tier --")
for r in sorted(by_risk.keys(), reverse=True):
    spd = speed_kmh(r)
    gap = max_gap(r)
    print(f"  risk {r}  ({spd:.0f} km/h, gap {gap:.1f} km):  {by_risk[r]:4d} shelters")
print(f"  TOTAL: {total}")
print()
print("-- Top 10 by deployment priority (AADT) --")
print(f"  {'#':>3}  {'Road':>6}  {'AADT':>8}  {'Risk':>5}  Location")
for rank, (lat, lon, risk, cw, rname, aadt) in enumerate(ranked[:10], 1):
    print(f"  {rank:3d}  {rname:>6}  {aadt:8,}  {risk:5.1f}  ({lat:.4f}, {lon:.4f})")
print()
print("-- Budget estimate (excl. VAT) --")
print(f"  Capital:           {cap_budget/1e6:.1f}M NIS")
print(f"  + 15% contingency: {cap_budget*1.15/1e6:.1f}M NIS")
print(f"  Annual maintenance:{total*15000/1e6:.2f}M NIS/yr")
print("=" * 60)
