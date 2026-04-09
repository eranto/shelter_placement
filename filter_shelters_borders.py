"""
Filter any shelter CSV to only include points within Israel's 1967 Green Line borders.

Applies two layers of filtering:
  1. israel_1967_filter.in_1967_israel() — the base geometric filter
  2. Additional strict rules targeting known gaps in the base filter:
       - Lebanon border: base filter allows too high a latitude in the middle section
       - West Bank (Bethlehem/Hebron): polygon western boundary is too far east
       - Dead Sea eastern shore: no base rule covers lat 31.0-31.8 east of lon 35.46
       - Arava valley: tolerance of 0.05 is too generous; also excludes roads that
         run east of Route 90 (lon > 35.15) which are in Jordan

Usage:
  python filter_shelters_borders.py                   # processes default files
  python filter_shelters_borders.py file1.csv ...     # processes named files

For each input file the script:
  1. Reads all rows and applies the combined filter to every (lat, lon) pair
  2. Reports removed shelters and the rule that caught each one
  3. Overwrites the file with the filtered rows (original backed up as *.bak)

Requires columns named 'lat' and 'lon' (case-insensitive).
"""

import csv, sys, shutil
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from israel_1967_filter import in_1967_israel

DEFAULT_FILES = [
    HERE / "shelters_priority_final.csv",
    HERE / "shelters_final_placements.csv",
]

# ── Strict additional rules ───────────────────────────────────────────────────
# West Bank tighter western boundary (Bethlehem / Hebron corridor).
# Each tuple is (lat, lon) going south; points EAST of the interpolated
# boundary line at a given latitude are in the West Bank.
TIGHT_WB_WEST = [
    (31.82, 35.19),   # Ramallah corridor (consistent with base filter)
    (31.72, 35.15),   # South Jerusalem / north Bethlehem (tighter than base 35.18)
    (31.62, 35.11),   # South Bethlehem (tighter than base 35.13)
    (31.52, 34.99),   # Hebron north (tighter than base 35.09)
    (31.35, 34.97),   # Hebron south
]

def _wb_boundary_lon(lat):
    """Interpolate the West Bank western boundary longitude at `lat`."""
    for i in range(len(TIGHT_WB_WEST) - 1):
        lat1, lon1 = TIGHT_WB_WEST[i]
        lat2, lon2 = TIGHT_WB_WEST[i + 1]
        if lat2 <= lat <= lat1:
            t = (lat - lat1) / (lat2 - lat1)
            return lon1 + t * (lon2 - lon1)
    return None

def strict_in_israel(lat, lon):
    """
    Returns (True, '') if the point is within 1967 Israel,
    or (False, reason) if it should be excluded.
    """
    # ── Layer 1: base filter ──────────────────────────────────────────────────
    if not in_1967_israel(lat, lon):
        return False, 'base filter (in_1967_israel)'

    # ── Layer 2: Lebanon border ───────────────────────────────────────────────
    # The base filter interpolates the Lebanon limit up to ~33.16 in the
    # middle section (lon 35.1-35.5). The actual border stays at ~33.07-33.08
    # throughout that stretch.
    if lon <= 35.50 and lat > 33.075:
        return False, f'Lebanon border (lat {lat:.4f} > 33.075 at lon {lon:.4f})'

    # ── Layer 3: West Bank — tighter Bethlehem/Hebron boundary ───────────────
    # Base filter polygon western boundary is too far east in this corridor,
    # allowing Route 60 (Bethlehem) and roads in the Hebron hills through.
    if 31.35 <= lat <= 31.82:
        boundary = _wb_boundary_lon(lat)
        if boundary is not None and lon > boundary:
            return False, f'West Bank tight boundary (lon {lon:.4f} > {boundary:.4f} at lat {lat:.4f})'

    # ── Layer 4: Dead Sea eastern shore / Jordan ──────────────────────────────
    # Route 90 along the Dead Sea western shore runs at ~lon 35.38-35.45.
    # Points east of lon 35.46 in this latitude band are on the Dead Sea
    # surface or the Jordanian/Palestinian eastern shore.
    if 31.0 <= lat <= 31.8 and lon > 35.46:
        return False, f'Dead Sea east of western shore (lon {lon:.4f} > 35.46)'

    # ── Layer 5: Arava valley — east of Route 90 ─────────────────────────────
    # Route 90 in the Arava runs at ~lon 35.0-35.1. Any road at lon > 35.15
    # in this latitude band is east of Route 90 and likely in Jordan.
    if 29.5 <= lat < 31.0 and lon > 35.15:
        return False, f'Arava east of Route 90 corridor (lon {lon:.4f} > 35.15)'

    return True, ''

# ── Helpers ───────────────────────────────────────────────────────────────────
def find_col(headers, name):
    for h in headers:
        if h.strip().lower() == name.lower():
            return h
    return None

def filter_csv(path):
    path = Path(path)
    if not path.exists():
        print(f"  SKIP  {path.name} — file not found")
        return

    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    lat_col = find_col(headers, 'lat')
    lon_col = find_col(headers, 'lon')
    if not lat_col or not lon_col:
        print(f"  SKIP  {path.name} — no lat/lon columns (headers: {headers})")
        return

    kept, removed = [], []
    for r in rows:
        try:
            lat = float(r[lat_col])
            lon = float(r[lon_col])
        except (ValueError, TypeError):
            kept.append(r)
            continue
        ok, reason = strict_in_israel(lat, lon)
        if ok:
            kept.append(r)
        else:
            removed.append((r, reason))

    print(f"\n  {path.name}")
    print(f"    Total: {len(rows)}  |  Kept: {len(kept)}  |  Removed: {len(removed)}")

    if removed:
        for r, reason in removed:
            road = r.get('road', r.get('road_name', ''))
            print(f"    REMOVED  rank={r.get('rank','?'):>4}  "
                  f"({r[lat_col]}, {r[lon_col]})  road={road}")
            print(f"             rule: {reason}")
    else:
        print(f"    All shelters within borders — no changes needed.")
        return

    backup = path.with_suffix('.csv.bak')
    shutil.copy(path, backup)
    print(f"    Backup saved → {backup.name}")

    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(kept)
    print(f"    Saved filtered file → {path.name}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    files = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_FILES
    print(f"Filtering {len(files)} file(s) against 1967 Green Line borders (strict mode)...\n")
    for f in files:
        filter_csv(f)
    print("\nDone.")
