"""
Geographic filter for Israel's 1967 Green Line borders.

Provides:
  in_1967_israel(lat, lon)   — base geometric filter (bounding box + polygons)
  strict_in_israel(lat, lon) — strict filter with additional rules for known gaps
  filter_segment(seg)        — True if a road segment midpoint is within Israel
  filter_csv(path)           — filter a shelter CSV in-place

The strict filter layers:
  1. Base bounding box + Lebanon/Golan/Jordan/WestBank/Gaza/Sinai checks
  2. Lebanon border: tightened to lat 33.075 in the middle section
  3. West Bank Bethlehem/Hebron corridor: tighter western boundary polyline
  4. Dead Sea eastern shore: lon > 35.46 between lat 31.0–31.8
  5. Arava valley: Israel–Jordan border formula without tolerance
  6. South of Eilat: lon > 34.97 → Aqaba/Jordan
  7. Jenin district: lon > 35.10 between lat 32.45–32.56

Usage (as a script):
  python filter_shelters_borders.py                   # processes default files
  python filter_shelters_borders.py file1.csv ...     # processes named files
"""

import csv, math, sys, shutil
from pathlib import Path

HERE = Path(__file__).parent

# ── Base filter (formerly israel_1967_filter.py) ──────────────────────────────

def _pip(lat, lon, poly):
    """Point-in-polygon test (ray casting). poly = list of (lat, lon)."""
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

# West Bank Green Line polygon — a point INSIDE is in the West Bank.
WEST_BANK = [
    (32.56, 35.19), (32.50, 35.19), (32.48, 35.12),
    (32.35, 35.05), (32.30, 35.00), (32.18, 34.97),
    (32.08, 34.99), (31.88, 34.97), (31.82, 35.19),
    (31.72, 35.18), (31.62, 35.13), (31.52, 35.09),
    (31.35, 35.03), (31.35, 35.57), (31.50, 35.57),
    (31.78, 35.57), (32.00, 35.57), (32.20, 35.57),
    (32.47, 35.57), (32.56, 35.52), (32.56, 35.19),
]

GAZA = [
    (31.61, 34.28), (31.61, 34.60), (31.42, 34.53),
    (31.22, 34.30), (31.22, 34.22), (31.61, 34.28),
]

def in_1967_israel(lat, lon):
    """Return True if (lat, lon) is within Israel's pre-1967 / Green Line borders."""
    if lat < 29.45 or lat > 33.35: return False
    if lon < 34.15 or lon > 35.70: return False

    # Lebanon / Syria border
    if lon <= 35.10:
        if lat > 33.07: return False
    else:
        leb_lat_limit = 33.07 + (lon - 35.10) / (35.65 - 35.10) * (33.27 - 33.07)
        if lat > leb_lat_limit: return False

    # Golan Heights
    if 32.65 < lat <= 32.88 and lon > 35.63: return False
    if lat > 32.88 and lon > 35.62: return False

    # Jordan / east of Jordan River
    if 31.0 <= lat <= 32.65 and lon > 35.57: return False
    if 29.56 <= lat < 31.0:
        arava_border = 35.00 + (lat - 29.56) / (31.05 - 29.56) * (35.42 - 35.00)
        if lon > arava_border + 0.05: return False

    # West Bank polygon
    if _pip(lat, lon, WEST_BANK): return False

    # Gaza Strip
    if _pip(lat, lon, GAZA): return False

    # Sinai / Egypt
    if lat < 31.24:
        t = (lat - 31.24) / (29.56 - 31.24)
        border_lon = 34.24 + t * (34.95 - 34.24)
        if lon < border_lon - 0.05: return False

    # South of Eilat
    if lat < 29.56 and lon < 34.88: return False

    return True


def filter_segment(seg):
    """Return True if the road segment midpoint is within 1967 Israel."""
    geom = seg.get('geom', [])
    if not geom:
        return False
    lats = [p[0] for p in geom]
    lons = [p[1] for p in geom]
    mlat = sum(lats) / len(lats)
    mlon = sum(lons) / len(lons)
    return in_1967_israel(mlat, mlon)

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
    (31.72, 35.14),   # South Jerusalem / north Bethlehem
    (31.67, 35.10),   # Gush Etzion / road 367 area
    (31.65, 35.05),   # Bethlehem south (catches rank 225)
    (31.62, 35.02),   # Tarqumia corridor (catches rank 234)
    (31.59, 34.95),   # Hebron north / route 35 area (catches rank 207)
    (31.52, 34.95),   # Hebron center (catches rank 218 via flat boundary)
    (31.48, 34.95),   # Hebron south (catches rank 205)
    (31.40, 34.93),   # South Hebron hills (catches rank 200)
    (31.35, 34.93),   # South Hebron hills tip
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
        return False, 'base filter'

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

    # ── Layer 5: Arava valley — east of Israel–Jordan border ─────────────────
    # The border runs as a straight line from Eilat/Aqaba (29.56, 35.00) to
    # the Dead Sea south (31.05, 35.42). Use that formula without tolerance.
    if 29.5 <= lat < 31.0:
        arava_border = 35.00 + (lat - 29.56) / (31.05 - 29.56) * (35.42 - 35.00)
        if lon > arava_border:
            return False, f'Arava east of Israel–Jordan border (lon {lon:.4f} > {arava_border:.4f})'

    # ── Layer 6: South of Eilat — Aqaba / Jordan east of Eilat ───────────────
    # Below Eilat latitude (29.56°N) the Israel strip is very narrow.
    # Points east of ~lon 34.97 are in Jordan / Gulf of Aqaba eastern shore.
    if lat < 29.56 and lon > 34.97:
        return False, f'Aqaba/Jordan south of Eilat (lon {lon:.4f} > 34.97)'

    # ── Layer 7: Jenin district — tighter western boundary ───────────────────
    # Base filter polygon has WB boundary at lon 35.19 at lat 32.50, but the
    # actual Green Line is ~35.10 here (catches rank 379, road 596).
    if 32.45 <= lat <= 32.56 and lon > 35.10:
        return False, f'Jenin district WB (lon {lon:.4f} > 35.10 at lat {lat:.4f})'

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
