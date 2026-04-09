"""
Geographic filter: returns True only for points within Israel's 1967 Green Line.

Excludes:
  - Gaza Strip
  - West Bank (Judea & Samaria)
  - Golan Heights  (captured 1967, annexed 1981 — excluded per user request)
  - Sinai / Egypt
  - Jordan (east of Jordan River)
  - Lebanon / Syria
"""

import math


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


# ── West Bank Green Line polygon (1949 armistice / 1967 border) ──────────────
# A point INSIDE this polygon is in the West Bank (outside 1967 Israel).
# The polygon is ordered clockwise starting from the NW corner.
WEST_BANK = [
    # Wadi Ara gap / north Green Line — Line enters east of Megiddo
    (32.56, 35.19),
    # Jenin district (east of Wadi Ara valley, which is IN Israel)
    (32.50, 35.19),
    (32.48, 35.12),
    # Green Line curves SE toward Tulkarm
    (32.35, 35.05),
    (32.30, 35.00),
    # Qalqilya bulge
    (32.18, 34.97),
    # Rosh HaAyin / Modi'in corridor
    (32.08, 34.99),
    # Latrun
    (31.88, 34.97),
    # Jerusalem north
    (31.82, 35.19),
    # Jerusalem south
    (31.72, 35.18),
    # Bethlehem south
    (31.62, 35.13),
    # Hebron area
    (31.52, 35.09),
    # South Hebron hills — West Bank southern tip ~lat 31.35
    (31.35, 35.03),
    (31.35, 35.57),   # West Bank east boundary continues north along Dead Sea
    # Dead Sea / Jordan River east bank
    (31.50, 35.57),
    (31.78, 35.57),
    (32.00, 35.57),
    (32.20, 35.57),
    (32.47, 35.57),
    # Beit She'an / Jordan River meets Green Line
    (32.56, 35.52),
    # Back north along the Green Line east of Wadi Ara
    (32.56, 35.19),
]

# ── Gaza Strip polygon ────────────────────────────────────────────────────────
GAZA = [
    (31.61, 34.28),   # NW corner (Mediterranean coast)
    (31.61, 34.60),   # Erez crossing / north-east corner (wider to catch all)
    (31.42, 34.53),   # Mid-east side
    (31.22, 34.30),   # Rafah south-east
    (31.22, 34.22),   # Rafah coast
    (31.61, 34.28),   # close
]


def in_1967_israel(lat, lon):
    """
    Returns True if (lat, lon) is within Israel's pre-1967 / Green Line borders.
    """
    # ── 1. Global bounding box ─────────────────────────────────────────────
    if lat < 29.45 or lat > 33.35:
        return False
    if lon < 34.15 or lon > 35.70:
        return False

    # ── 2. Lebanon / Syria border ─────────────────────────────────────────
    # The Lebanon border rises from ~33.07°N at the coast to ~33.27°N in the
    # east. Approximate it as a straight line in longitude.
    if lon <= 35.10:
        if lat > 33.07:
            return False
    else:
        leb_lat_limit = 33.07 + (lon - 35.10) / (35.65 - 35.10) * (33.27 - 33.07)
        if lat > leb_lat_limit:
            return False

    # ── 3. Golan Heights (captured 1967, annexed 1981) ────────────────────
    # South of the Sea of Galilee NE corner (lat 32.65–32.88):
    # Golan starts just east of the Sea of Galilee eastern shore (~lon 35.63)
    if 32.65 < lat <= 32.88 and lon > 35.63:
        return False
    # North of the Sea of Galilee NE corner (lat > 32.88):
    # Jordan River runs at ~lon 35.59–35.62; Golan starts just east of it
    if lat > 32.88 and lon > 35.62:
        return False

    # ── 4. Jordan / east of Jordan River ──────────────────────────────────
    # Jordan Valley (lat 31.0–32.65): Jordan River at ~35.55–35.58°E
    if 31.0 <= lat <= 32.65 and lon > 35.57:
        return False
    # Arava valley (lat 29.56–31.0): Israel–Jordan border runs NE from
    # Eilat/Aqaba (29.56, 35.00) to Dead Sea south (31.05, 35.42).
    # Approximate as a straight line.
    if 29.56 <= lat < 31.0:
        arava_border = 35.00 + (lat - 29.56) / (31.05 - 29.56) * (35.42 - 35.00)
        if lon > arava_border + 0.05:   # small tolerance for road on Israeli side
            return False

    # ── 5. West Bank (Green Line polygon) ─────────────────────────────────
    if _pip(lat, lon, WEST_BANK):
        return False

    # ── 6. Gaza Strip ─────────────────────────────────────────────────────
    if _pip(lat, lon, GAZA):
        return False

    # ── 7. Sinai / Egypt — western border ─────────────────────────────────
    # The Israel–Egypt border runs as a straight line from:
    #   Eilat / Taba:  (29.56°N, 34.95°E)  →  Rafah: (31.24°N, 34.24°E)
    # Points south of Rafah latitude that are WEST of this line are in Sinai.
    if lat < 31.24:
        # Longitude of the border at this latitude
        t = (lat - 31.24) / (29.56 - 31.24)          # 0 at Rafah, 1 at Eilat
        border_lon = 34.24 + t * (34.95 - 34.24)
        if lon < border_lon - 0.05:                    # small tolerance
            return False

    # ── 8. Additional exclusion: south of Eilat ────────────────────────────
    # Eilat is Israel's southernmost city at ~29.56°N. Anything appreciably
    # south of that with lon > 34.9 is the Gulf of Aqaba / Red Sea area.
    # The road to Eilat runs along the coast — keep lon ≥ 34.88 south of 29.7.
    if lat < 29.56 and lon < 34.88:
        return False

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


if __name__ == '__main__':
    # Quick sanity-check
    tests = [
        # Inside Israel
        ((32.08, 34.78), True,  "Tel Aviv"),
        ((31.25, 34.79), True,  "Beer Sheva"),
        ((32.92, 35.07), True,  "Acre"),
        ((33.20, 35.57), True,  "Kiryat Shmona"),
        ((29.56, 34.95), True,  "Eilat"),
        # Outside
        ((32.50, 35.30), False, "West Bank / Nablus"),
        ((31.53, 35.10), False, "West Bank / Hebron"),
        ((31.40, 34.38), False, "Gaza Strip"),
        ((31.90, 35.22), False, "West Bank / Jerusalem E"),
        ((29.70, 34.17), False, "Sinai"),
        ((29.68, 34.57), False, "Sinai south"),
        ((32.99, 35.69), False, "Golan Heights / Katzrin"),
        ((33.07, 35.63), False, "Golan Heights / Route 918"),
        ((32.00, 35.62), False, "Jordan"),
        ((33.50, 35.40), False, "Lebanon"),
    ]
    ok = 0
    for (lat, lon), expected, label in tests:
        result = in_1967_israel(lat, lon)
        status = "✓" if result == expected else "✗ FAIL"
        print(f"  {status}  {label:35s} ({lat:.2f},{lon:.2f})  "
              f"expected={expected} got={result}")
        if result == expected:
            ok += 1
    print(f"\n{ok}/{len(tests)} passed")
