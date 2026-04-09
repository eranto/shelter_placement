"""
Re-run Gonzalez shelter placement with priority zones.

Standard roads   : 5.0-minute alarm standard
Jerusalem area   : 3.0-minute alarm standard  (unchanged)
North border     : 4.5-minute alarm standard  (NEW)
Gaza envelope    : 4.5-minute alarm standard  (NEW)

Priority zones:
  North border  — lat > 33.05  (above Nahariya / upper Galilee)
  Gaza envelope — lat < 31.60 AND lon < 34.90

Saves: shelter_points_priority.pkl
       (same 5-tuple format as shelter_points_traffic.pkl)
"""

import json, math, pickle, heapq, os, sys
import numpy as np
from collections import defaultdict

np.random.seed(7)

HERE      = "/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006"
sys.path.insert(0, HERE)
CACHE     = f"{HERE}/osm_roads_traffic_cache.pkl"
OUT_CKPT  = f"{HERE}/shelter_points_priority.pkl"

# ── Zone definitions ──────────────────────────────────────────────────────────
TIME_STD   = 5.0   # minutes — standard roads
TIME_JER   = 3.0   # minutes — Jerusalem
TIME_PRIOR = 5.0   # minutes — north border + Gaza envelope

JER_LAT = (31.72, 31.87)
JER_LON = (34.92, 35.18)

def zone_time_limit(lat, lon):
    if JER_LAT[0] <= lat <= JER_LAT[1] and JER_LON[0] <= lon <= JER_LON[1]:
        return TIME_JER
    if lat > 33.05:                        # north border
        return TIME_PRIOR
    if lat < 31.60 and lon < 34.90:        # Gaza envelope
        return TIME_PRIOR
    return TIME_STD

# ── Helpers ───────────────────────────────────────────────────────────────────
def seg_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

def road_length_km(pts):
    return sum(seg_km(pts[i], pts[i+1]) for i in range(len(pts)-1))

def interpolate_km(wpts, step_km):
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total < step_km * 0.4:
        return []
    dists = list(np.arange(0, total, step_km)) + [total]
    pts = []
    for tgt in sorted(set(dists)):
        seg = min(np.searchsorted(cum, tgt, side='right')-1, len(wpts)-2)
        sl  = cum[seg+1] - cum[seg]
        t   = 0 if sl == 0 else (tgt-cum[seg])/sl
        pts.append((
            wpts[seg][0] + t*(wpts[seg+1][0]-wpts[seg][0]),
            wpts[seg][1] + t*(wpts[seg+1][1]-wpts[seg][1]),
        ))
    return pts

def speed_kmh(risk, maxspeed=None):
    if maxspeed is not None:
        return max(30.0, min(130.0, float(maxspeed)))
    if risk >= 4.0: return 70.0
    if risk >= 3.0: return 80.0
    if risk >= 2.0: return 90.0
    return 110.0

def lanes_cap_w(lanes):
    if lanes is None: return 1.0
    if lanes >= 5: return 3.0
    return {1:1.0, 2:1.5, 3:2.0, 4:2.5}.get(lanes, 1.0)

def dijkstra_from(source, adj, N):
    dist = [math.inf] * N
    dist[source] = 0.0
    heap = [(0.0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]: continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist

# ── Load OSM cache & build merged road list ───────────────────────────────────
from filter_shelters_borders import filter_segment, in_1967_israel

print("Loading OSM road cache...")
all_roads = pickle.load(open(CACHE, 'rb'))
raw_roads = [s for s in all_roads if filter_segment(s)]
print(f"  {len(all_roads)} segments in cache → {len(raw_roads)} within 1967 Israel borders.")

# Group by route ref and compute median lanes/speed
from collections import Counter

def median_val(vals):
    v = sorted(x for x in vals if x is not None)
    if not v: return None
    return v[len(v)//2]

ref_groups = defaultdict(list)
for seg in raw_roads:
    ref = seg.get('name','').split(';')[0].strip()
    if ref:
        ref_groups[ref].append(seg)

RISK_MAP = {'motorway':4.0,'trunk':3.5,'primary':2.5,'secondary':2.0,'tertiary':1.5}

merged = []
for ref, segs in ref_groups.items():
    hw        = segs[0].get('highway','primary')
    med_lanes = median_val([s.get('lanes') for s in segs])
    med_speed = median_val([s.get('maxspeed') for s in segs])
    cap_w     = lanes_cap_w(int(round(med_lanes)) if med_lanes else None)
    risk      = RISK_MAP.get(hw, 2.0)
    for seg in segs:
        geom = seg.get('geom', [])
        if len(geom) >= 2:
            merged.append({
                'name':     ref,
                'highway':  hw,
                'geom':     geom,
                'risk':     risk,
                'lanes':    med_lanes,
                'maxspeed': med_speed,
                'cap_w':    cap_w,
            })

total_km = sum(road_length_km(rd['geom']) for rd in merged)
print(f"  {len(merged)} road chains, {total_km:.0f} km total")

# ── Build graph ───────────────────────────────────────────────────────────────
STEP_KM     = 0.5
JUNCTION_KM = 0.1
CELL_DEG    = 0.005

print("Building road network graph...")
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

# Dedup coincident nodes
pos_to_id  = {}
node_remap = {}
new_nodes  = []
for nid, nd in enumerate(nodes):
    key = (round(nd[0],4), round(nd[1],4))
    if key in pos_to_id:
        node_remap[nid] = pos_to_id[key]
    else:
        new_id = len(new_nodes)
        pos_to_id[key] = new_id
        node_remap[nid] = new_id
        new_nodes.append(nd)

road_node_seqs = [[node_remap[n] for n in seq] for seq in road_node_seqs]
nodes = new_nodes
N     = len(nodes)
print(f"  {N} unique demand nodes")

# Adjacency
adj = defaultdict(list)
for seq in road_node_seqs:
    for i in range(len(seq)-1):
        a, b = seq[i], seq[i+1]
        d_km = seg_km((nodes[a][0],nodes[a][1]), (nodes[b][0],nodes[b][1]))
        spd  = speed_kmh(nodes[a][2], nodes[a][4])
        tt   = d_km / spd * 60.0
        adj[a].append((b, tt))
        adj[b].append((a, tt))

# Junction edges
grid = defaultdict(list)
for nid, nd in enumerate(nodes):
    cell = (int(nd[0]/CELL_DEG), int(nd[1]/CELL_DEG))
    grid[cell].append(nid)

node_road = {}
for rid, seq in enumerate(road_node_seqs):
    for nid in seq:
        node_road[nid] = rid

j_edges = 0
for nid, nd in enumerate(nodes):
    lat, lon = nd[0], nd[1]
    cr, cc = int(lat/CELL_DEG), int(lon/CELL_DEG)
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            for other in grid.get((cr+dr, cc+dc), []):
                if other <= nid: continue
                if node_road.get(nid) == node_road.get(other): continue
                if seg_km((lat,lon),(nodes[other][0],nodes[other][1])) <= JUNCTION_KM:
                    adj[nid].append((other, 0.0))
                    adj[other].append((nid, 0.0))
                    j_edges += 1

print(f"  {j_edges} junction edges, {sum(len(v) for v in adj.values())//2} total edges")

junction_node_set = set()
for nid in range(N):
    for other, w in adj[nid]:
        if w == 0.0 and node_road.get(nid) != node_road.get(other):
            junction_node_set.add(nid)
            break

# ── Zone assignment ───────────────────────────────────────────────────────────
node_tlimit = [zone_time_limit(nodes[i][0], nodes[i][1]) for i in range(N)]

zone_counts = Counter(node_tlimit)
print(f"  Zone breakdown:")
for t, cnt in sorted(zone_counts.items()):
    label = {TIME_JER:'Jerusalem', TIME_PRIOR:'Priority (N+Gaza)', TIME_STD:'Standard'}[t]
    print(f"    {t:.1f} min  ({label}): {cnt:,} nodes")

# ── Gonzalez algorithm ────────────────────────────────────────────────────────
JUNCTION_BONUS    = 0.30
TRAFFIC_BONUS_SCL = 0.10

def node_score(nid):
    limit  = node_tlimit[nid]
    j_bon  = JUNCTION_BONUS if nid in junction_node_set else 0.0
    t_bon  = TRAFFIC_BONUS_SCL * (nodes[nid][5] - 1.0)
    return dist_to_nearest[nid] / limit + j_bon + t_bon

def all_covered():
    return all(dist_to_nearest[i] <= node_tlimit[i] for i in range(N))

print(f"\nRunning Gonzalez algorithm "
      f"(std={TIME_STD} min, jer={TIME_JER} min, priority={TIME_PRIOR} min)...")

INF             = math.inf
dist_to_nearest = [INF] * N
highest_risk    = max(range(N), key=lambda i: nodes[i][2])
shelter_ids     = []
iteration       = 0

while True:
    chosen = highest_risk if iteration == 0 else (
        None if all_covered() else max(range(N), key=node_score)
    )
    if chosen is None:
        break

    shelter_ids.append(chosen)
    iteration += 1

    d_from = dijkstra_from(chosen, adj, N)
    for i in range(N):
        if d_from[i] < dist_to_nearest[i]:
            dist_to_nearest[i] = d_from[i]

    current_max = max(dist_to_nearest)
    lat_c, lon_c = nodes[chosen][0], nodes[chosen][1]
    tlim = node_tlimit[chosen]
    zone_tag = ('[JER]' if tlim == TIME_JER else
                '[PRIO]' if tlim == TIME_PRIOR else '     ')
    print(f"  Shelter {iteration:3d}: ({lat_c:.4f},{lon_c:.4f})  "
          f"risk={nodes[chosen][2]:.1f}  cap_w={nodes[chosen][5]:.1f}  "
          f"{zone_tag}  max_remaining={current_max:.2f} min")

final_max = max(dist_to_nearest)
print(f"\nPlacement complete: {len(shelter_ids)} shelters, "
      f"max travel time = {final_max:.2f} min")

# Count shelters by zone
zone_shelters = Counter(
    ('jerusalem' if node_tlimit[n]==TIME_JER else
     'priority'  if node_tlimit[n]==TIME_PRIOR else 'standard')
    for n in shelter_ids
)
print("Shelters by zone:", dict(zone_shelters))

shelter_points = [
    (nodes[n][0], nodes[n][1], nodes[n][2], nodes[n][5], nodes[n][3])
    for n in shelter_ids
]

# Final border purge — remove any node the 1967 filter still rejects
before_purge = len(shelter_points)
shelter_points = [p for p in shelter_points if in_1967_israel(p[0], p[1])]
purged = before_purge - len(shelter_points)
if purged:
    print(f"Border purge: removed {purged} shelter(s) outside 1967 Israel "
          f"({len(shelter_points)} remain)")

pickle.dump((shelter_points, final_max), open(OUT_CKPT, 'wb'))
print(f"Saved: {OUT_CKPT}")
