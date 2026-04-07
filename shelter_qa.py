"""
Quality analysis of road_shelters_optimized.py results.
Re-runs the same data pipeline up to shelter_points, then analyses:
  - Pairs closer than threshold
  - Coverage gaps
  - Distribution by risk / region
"""
import math, heapq, pickle, os, sys
import numpy as np

# ── Re-use helpers from optimised script ─────────────────────────────────────
BASE = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report"
CACHE = os.path.join(BASE, "osm_roads_cache.pkl")

def seg_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat**2 + dlon**2)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── Load shelter data by re-running the key parts of the optimised script ────
# We import the module's globals by exec-ing it into a dict.
print("Loading shelter data (re-running optimised script) …")
ns = {}
exec(open(os.path.join(BASE, "road_shelters_optimized.py")).read(), ns)
shelter_points = ns["shelter_points"]   # list of (lat, lon, risk)
print(f"Loaded {len(shelter_points)} shelters.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 1. CLOSE-PAIR ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
THRESHOLDS = [1.0, 1.5, 2.0, 3.0, 5.0]

print("=" * 65)
print("CLOSE-PAIR ANALYSIS  (straight-line distance)")
print("=" * 65)

for thr in THRESHOLDS:
    pairs = []
    pts = shelter_points
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = haversine_km(pts[i][0], pts[i][1], pts[j][0], pts[j][1])
            if d < thr:
                pairs.append((d, i, j))
    pairs.sort()
    print(f"\n  < {thr:.1f} km : {len(pairs)} pairs")
    for d, i, j in pairs[:15]:
        print(f"    {d:.3f} km  shelter#{i+1} ({pts[i][0]:.4f},{pts[i][1]:.4f}) r={pts[i][2]}"
              f"  ↔  shelter#{j+1} ({pts[j][0]:.4f},{pts[j][1]:.4f}) r={pts[j][2]}")
    if len(pairs) > 15:
        print(f"    … and {len(pairs)-15} more")

# ─────────────────────────────────────────────────────────────────────────────
# 2. DISTANCE DISTRIBUTION BETWEEN CONSECUTIVE SHELTERS (per risk tier)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("NEAREST-NEIGHBOUR DISTANCE DISTRIBUTION")
print("=" * 65)
pts = shelter_points
nn_dists = []
for i, (lat, lon, risk) in enumerate(pts):
    min_d = min(
        haversine_km(lat, lon, pts[j][0], pts[j][1])
        for j in range(len(pts)) if j != i
    )
    nn_dists.append(min_d)

nn_arr = np.array(nn_dists)
print(f"  Min NN distance : {nn_arr.min():.3f} km  (shelter #{nn_arr.argmin()+1})")
print(f"  Mean NN distance: {nn_arr.mean():.2f} km")
print(f"  Median          : {np.median(nn_arr):.2f} km")
print(f"  Max NN distance : {nn_arr.max():.2f} km  (shelter #{nn_arr.argmax()+1})")

# Histogram buckets
buckets = [0, 1, 2, 3, 5, 8, 12, 20, 999]
labels  = ["<1", "1-2", "2-3", "3-5", "5-8", "8-12", "12-20", ">20"]
counts  = [0] * (len(buckets) - 1)
for d in nn_dists:
    for k in range(len(labels)):
        if buckets[k] <= d < buckets[k+1]:
            counts[k] += 1
            break
print("\n  NN distance histogram:")
for lbl, cnt in zip(labels, counts):
    bar = "█" * int(cnt / max(counts) * 30)
    print(f"    {lbl:>6} km : {cnt:3d}  {bar}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. SHELTERS WITH NN < 2 km — listed for review
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("SHELTERS WITH NEAREST NEIGHBOUR < 2 km  (candidates for removal)")
print("=" * 65)
close_shelters = [(i, nn_dists[i]) for i in range(len(pts)) if nn_dists[i] < 2.0]
close_shelters.sort(key=lambda x: x[1])
print(f"  {len(close_shelters)} shelters have a neighbour within 2 km\n")
for i, d in close_shelters[:40]:
    lat, lon, risk = pts[i]
    # find the actual nearest neighbour
    nn_j = min((j for j in range(len(pts)) if j != i),
               key=lambda j: haversine_km(lat, lon, pts[j][0], pts[j][1]))
    print(f"  #{i+1:3d} ({lat:.4f},{lon:.4f}) r={risk:.1f}  ↔  "
          f"#{nn_j+1:3d} ({pts[nn_j][0]:.4f},{pts[nn_j][1]:.4f}) r={pts[nn_j][2]:.1f}  "
          f"d={d:.3f} km")
if len(close_shelters) > 40:
    print(f"  … and {len(close_shelters)-40} more")

# ─────────────────────────────────────────────────────────────────────────────
# 4. REGION BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("REGION BREAKDOWN")
print("=" * 65)
regions = {
    "North (Galilee / Golan approach)": lambda la, lo: la >= 32.8,
    "Haifa / Carmel":                   lambda la, lo: 32.5 <= la < 32.8,
    "Sharon / Center":                  lambda la, lo: 32.0 <= la < 32.5,
    "Tel Aviv metro":                   lambda la, lo: 31.9 <= la < 32.1 and lo < 35.0,
    "Jerusalem area":                   lambda la, lo: 31.72 <= la < 31.92 and 34.92 <= lo <= 35.25,
    "South (Negev)":                    lambda la, lo: 29.5 <= la < 31.3,
    "Gaza envelope":                    lambda la, lo: 31.2 <= la <= 31.7 and lo < 34.6,
}
for name, fn in regions.items():
    subset = [(la, lo, ri) for la, lo, ri in pts if fn(la, lo)]
    risks  = [ri for _, _, ri in subset]
    print(f"  {name:<35} {len(subset):3d} shelters  "
          f"avg_risk={sum(risks)/len(risks):.2f}" if risks else
          f"  {name:<35}   0 shelters")

print(f"\n  TOTAL : {len(pts)} shelters")

# ─────────────────────────────────────────────────────────────────────────────
# 5. SUSPICIOUS OUTLIERS  — shelters very far from any other shelter
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("ISOLATED SHELTERS (NN > 15 km — possibly correct for sparse Negev)")
print("=" * 65)
isolated = [(i, nn_dists[i]) for i in range(len(pts)) if nn_dists[i] > 15.0]
isolated.sort(key=lambda x: -x[1])
for i, d in isolated:
    lat, lon, risk = pts[i]
    print(f"  #{i+1:3d} ({lat:.4f},{lon:.4f}) r={risk:.1f}  NN={d:.1f} km")
if not isolated:
    print("  None found.")

print("\nDone.")
