"""
Quality analysis of shelter placement output.

Reads shelter data by importing optimize_shelters (re-runs the pipeline,
uses the local cache — takes ~2 min).

Reports:
  - Close-pair analysis at multiple distance thresholds
  - Nearest-neighbour distance distribution
  - Shelters with a neighbour under 2 km (candidates for review)
  - Region breakdown
  - Isolated shelters (possible coverage gaps)

Usage:
  python quality_analysis.py
"""

import math, os, sys
from pathlib import Path
import numpy as np

BASE = Path(__file__).parent

# ── Haversine distance ────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# ── Load shelter data by executing the optimization script ────────────────────
print("Loading shelter data (running optimization pipeline, uses cache) …")
ns = {}
exec(open(BASE / "optimize_shelters.py").read(), ns)
shelter_points = ns["shelter_points"]   # list of (lat, lon, risk)
print(f"\nLoaded {len(shelter_points)} shelters.\n")

pts = shelter_points

# ─────────────────────────────────────────────────────────────────────────────
# 1.  CLOSE-PAIR ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("CLOSE-PAIR ANALYSIS  (straight-line / haversine distance)")
print("=" * 65)

for thr in [1.0, 1.5, 2.0, 3.0, 5.0]:
    pairs = sorted(
        [(haversine_km(pts[i][0], pts[i][1], pts[j][0], pts[j][1]), i, j)
         for i in range(len(pts))
         for j in range(i+1, len(pts))
         if haversine_km(pts[i][0], pts[i][1], pts[j][0], pts[j][1]) < thr]
    )
    print(f"\n  < {thr:.1f} km : {len(pairs)} pairs")
    for d, i, j in pairs[:10]:
        print(f"    {d:.3f} km  #{i+1} ({pts[i][0]:.4f},{pts[i][1]:.4f}) r={pts[i][2]}"
              f"  ↔  #{j+1} ({pts[j][0]:.4f},{pts[j][1]:.4f}) r={pts[j][2]}")
    if len(pairs) > 10:
        print(f"    … and {len(pairs)-10} more")

# ─────────────────────────────────────────────────────────────────────────────
# 2.  NEAREST-NEIGHBOUR DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("NEAREST-NEIGHBOUR DISTANCE DISTRIBUTION")
print("=" * 65)

nn_dists = [
    min(haversine_km(pts[i][0], pts[i][1], pts[j][0], pts[j][1])
        for j in range(len(pts)) if j != i)
    for i in range(len(pts))
]
nn_arr = np.array(nn_dists)

print(f"  Min NN : {nn_arr.min():.3f} km  (shelter #{nn_arr.argmin()+1})")
print(f"  Mean   : {nn_arr.mean():.2f} km")
print(f"  Median : {np.median(nn_arr):.2f} km")
print(f"  Max NN : {nn_arr.max():.2f} km  (shelter #{nn_arr.argmax()+1})")

buckets = [0, 1, 2, 3, 5, 8, 12, 20, 999]
labels  = ["<1", "1-2", "2-3", "3-5", "5-8", "8-12", "12-20", ">20"]
counts  = [sum(1 for d in nn_dists if buckets[k] <= d < buckets[k+1])
           for k in range(len(labels))]
print("\n  Histogram:")
for lbl, cnt in zip(labels, counts):
    bar = "█" * int(cnt / max(counts, default=1) * 30)
    print(f"    {lbl:>6} km : {cnt:3d}  {bar}")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  SHELTERS WITH NN < 2 km
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("SHELTERS WITH NEAREST NEIGHBOUR < 2 km")
print("=" * 65)

close = sorted([(i, nn_dists[i]) for i in range(len(pts)) if nn_dists[i] < 2.0],
               key=lambda x: x[1])
print(f"  {len(close)} shelters\n")
for i, d in close[:30]:
    nn_j = min((j for j in range(len(pts)) if j != i),
               key=lambda j: haversine_km(pts[i][0], pts[i][1], pts[j][0], pts[j][1]))
    print(f"  #{i+1:3d} ({pts[i][0]:.4f},{pts[i][1]:.4f}) r={pts[i][2]:.1f}  ↔  "
          f"#{nn_j+1:3d} ({pts[nn_j][0]:.4f},{pts[nn_j][1]:.4f}) r={pts[nn_j][2]:.1f}  "
          f"d={d:.3f} km")
if len(close) > 30:
    print(f"  … and {len(close)-30} more")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  REGION BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("REGION BREAKDOWN")
print("=" * 65)

regions = {
    "North (Galilee / Lebanon border)": lambda la, lo: la >= 32.8,
    "Haifa / Carmel":                   lambda la, lo: 32.5 <= la < 32.8,
    "Sharon / Center":                  lambda la, lo: 32.0 <= la < 32.5,
    "Tel Aviv metro":                   lambda la, lo: 31.9 <= la < 32.1 and lo < 35.0,
    "Jerusalem area":                   lambda la, lo: 31.72 <= la < 31.92 and 34.92 <= lo <= 35.25,
    "South (Negev)":                    lambda la, lo: 29.5 <= la < 31.3,
    "Gaza envelope":                    lambda la, lo: 31.2 <= la <= 31.7 and lo < 34.6,
}
for name, fn in regions.items():
    subset = [(la, lo, ri) for la, lo, ri in pts if fn(la, lo)]
    if subset:
        avg_r = sum(ri for _, _, ri in subset) / len(subset)
        print(f"  {name:<38} {len(subset):3d} shelters  avg_risk={avg_r:.2f}")
    else:
        print(f"  {name:<38}   0 shelters")

print(f"\n  TOTAL: {len(pts)} shelters")

# ─────────────────────────────────────────────────────────────────────────────
# 5.  ISOLATED SHELTERS  (NN > 15 km)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("ISOLATED SHELTERS  (NN > 15 km — sparse road areas, expected in Negev)")
print("=" * 65)
isolated = sorted([(i, nn_dists[i]) for i in range(len(pts)) if nn_dists[i] > 15.0],
                  key=lambda x: -x[1])
if isolated:
    for i, d in isolated:
        print(f"  #{i+1:3d} ({pts[i][0]:.4f},{pts[i][1]:.4f}) r={pts[i][2]:.1f}  NN={d:.1f} km")
else:
    print("  None found.")

print("\nAnalysis complete.")
