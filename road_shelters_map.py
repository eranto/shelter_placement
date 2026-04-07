"""
Generate ~400 road shelter (מיגונית) locations along Israeli roads,
weighted heavily toward high-risk zones (Gaza envelope, northern border).
Outputs an interactive HTML map.
"""

import numpy as np
import folium
from folium.plugins import MarkerCluster
import json

np.random.seed(42)
OUTPUT = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_map.html"

# ── Road segments ──────────────────────────────────────────────────────────────
# Each entry: (display_name, [(lat, lon), ...], risk_weight)
# risk_weight: 1=normal, 2=elevated, 3=high, 4=very_high (Gaza/Lebanon border)
#
ROADS = [
    # ── Gaza envelope & south (highest risk) ──────────────────────────────
    ("כביש 232 (עוטף עזה)",
     [(31.416, 34.291), (31.382, 34.315), (31.354, 34.336),
      (31.318, 34.362), (31.275, 34.398), (31.242, 34.425)], 4.0),

    ("כביש 34 (עוטף עזה – נגב מערבי)",
     [(31.680, 34.558), (31.586, 34.510), (31.490, 34.476),
      (31.416, 34.450), (31.360, 34.430)], 3.5),

    ("כביש 35 (קרית גת – שדרות)",
     [(31.610, 34.773), (31.551, 34.703), (31.518, 34.622),
      (31.476, 34.547), (31.426, 34.494)], 3.5),

    ("כביש 25 (נגב מרכזי)",
     [(31.264, 34.798), (31.242, 34.625), (31.220, 34.430)], 3.0),

    ("כביש 40 (באר שבע–אשקלון)",
     [(31.680, 34.558), (31.556, 34.600), (31.435, 34.647),
      (31.270, 34.797)], 2.5),

    # ── צפון – גבול לבנון (סיכון גבוה) ────────────────────────────────────
    ("כביש 99 (גליל עליון – גבול לבנון)",
     [(33.250, 35.124), (33.224, 35.217), (33.197, 35.330),
      (33.172, 35.440), (33.115, 35.583), (33.081, 35.693)], 4.0),

    ("כביש 978 / 899 (קו הגבול)",
     [(33.272, 35.101), (33.248, 35.135), (33.220, 35.185),
      (33.188, 35.248), (33.155, 35.310), (33.098, 35.387),
      (33.072, 35.420)], 4.0),

    ("כביש 90 (עמק הירדן – צפון)",
     [(33.197, 35.550), (32.970, 35.490), (32.735, 35.575),
      (32.500, 35.535), (32.240, 35.499)], 2.5),

    ("כביש 85 (עכו–שפרעם–טבריה)",
     [(32.925, 35.083), (32.874, 35.156), (32.845, 35.258),
      (32.808, 35.388), (32.770, 35.491)], 2.0),

    ("כביש 65 (וואדי ערה – מגידו)",
     [(32.562, 35.185), (32.517, 35.104), (32.487, 35.001),
      (32.461, 34.942)], 1.8),

    # ── כביש 6 (חוצה ישראל) ─────────────────────────────────────────────
    ("כביש 6 (חוצה ישראל – מרכז)",
     [(32.080, 34.930), (32.200, 34.988), (32.350, 35.003),
      (32.500, 35.012), (32.650, 35.058), (32.800, 35.097)], 1.5),

    ("כביש 6 (חוצה ישראל – דרום)",
     [(31.700, 34.750), (31.850, 34.798), (32.000, 34.870),
      (32.080, 34.930)], 1.5),

    # ── כביש 1 (ת"א–ירושלים) ────────────────────────────────────────────
    ("כביש 1 (תל אביב–ירושלים)",
     [(32.082, 34.781), (31.975, 34.908), (31.905, 34.987),
      (31.850, 35.065), (31.793, 35.172), (31.782, 35.216)], 1.8),

    # ── כביש 2 (חוף – צפון) ─────────────────────────────────────────────
    ("כביש 2 (גוש דן–חדרה–חיפה)",
     [(32.082, 34.781), (32.175, 34.832), (32.320, 34.870),
      (32.460, 34.924), (32.620, 34.961), (32.820, 34.981)], 1.4),

    # ── כביש 4 (חוף – דרום) ─────────────────────────────────────────────
    ("כביש 4 (גוש דן–אשדוד–אשקלון)",
     [(32.082, 34.781), (31.985, 34.750), (31.870, 34.715),
      (31.760, 34.660), (31.680, 34.583)], 2.0),

    # ── כביש 90 (בקעת הירדן – דרום) ────────────────────────────────────
    ("כביש 90 (בקעת הירדן – ים המלח)",
     [(32.240, 35.499), (32.000, 35.488), (31.780, 35.430),
      (31.550, 35.436), (31.270, 35.450), (30.980, 35.434)], 2.5),

    # ── כביש 31 (הנגב) ──────────────────────────────────────────────────
    ("כביש 31 (באר שבע–ערד–מצדה)",
     [(31.270, 34.797), (31.267, 35.000), (31.262, 35.210),
      (31.190, 35.344)], 1.8),

    # ── כביש 40 (חצי האי סיני/נגב) ─────────────────────────────────────
    ("כביש 40 (ניצנה–מצפה רמון–אילת)",
     [(30.870, 34.430), (30.605, 34.803), (30.200, 34.950),
      (29.870, 35.022), (29.558, 34.948)], 2.0),

    # ── כבישים עירוניים ראשיים ──────────────────────────────────────────
    ("כביש 3 (שפלה)",
     [(31.990, 34.892), (31.869, 34.904), (31.780, 35.214)], 1.3),

    ("כביש 38 (בית שמש–ירושלים)",
     [(31.780, 35.214), (31.733, 35.005), (31.697, 34.990)], 1.3),

    ("כביש 79 (נצרת–עפולה–קישון)",
     [(32.700, 35.303), (32.626, 35.178), (32.590, 35.109)], 1.4),

    ("כביש 77 (עכו–נהריה–לבנון)",
     [(32.925, 35.083), (33.003, 35.097), (33.017, 35.100)], 2.0),

    ("כביש 75 (נצרת–עפולה)",
     [(32.700, 35.303), (32.665, 35.222), (32.606, 35.188)], 1.3),
]

# ── Shelter placement ──────────────────────────────────────────────────────────

def interpolate_road(waypoints, num_points):
    """Return num_points equally-spaced (lat, lon) along a polyline."""
    pts = np.array(waypoints)
    # cumulative distance along the polyline
    diffs = np.diff(pts, axis=0)
    seg_len = np.sqrt((diffs ** 2).sum(axis=1))
    cum = np.concatenate([[0], np.cumsum(seg_len)])
    total = cum[-1]
    if total == 0 or num_points < 1:
        return pts[:num_points] if num_points <= len(pts) else pts
    t_query = np.linspace(0, total, num_points)
    lats = np.interp(t_query, cum, pts[:, 0])
    lons = np.interp(t_query, cum, pts[:, 1])
    return list(zip(lats, lons))


TARGET = 400
total_weight = sum(w for _, _, w in ROADS)
# approximate km per road (rough)
def road_length_deg(waypoints):
    pts = np.array(waypoints)
    diffs = np.diff(pts, axis=0)
    return np.sqrt((diffs ** 2).sum(axis=1)).sum()

# Allocate shelters proportional to weight × length
allocations = []
for name, wpts, risk in ROADS:
    length = road_length_deg(wpts)
    allocations.append((name, wpts, risk, length, risk * length))

total_score = sum(a[4] for a in allocations)
shelter_points = []
road_shelter_counts = {}

for name, wpts, risk, length, score in allocations:
    n = max(1, round(TARGET * score / total_score))
    road_shelter_counts[name] = n
    pts = interpolate_road(wpts, n)
    # add small random jitter so shelters don't sit exactly on the centerline
    for lat, lon in pts:
        jlat = lat + np.random.uniform(-0.003, 0.003)
        jlon = lon + np.random.uniform(-0.004, 0.004)
        shelter_points.append((jlat, jlon, name, risk))

# trim / pad to exactly 400
if len(shelter_points) > TARGET:
    shelter_points = shelter_points[:TARGET]

print(f"Total shelters placed: {len(shelter_points)}")

# ── Build Folium map ───────────────────────────────────────────────────────────

m = folium.Map(
    location=[31.5, 35.0],
    zoom_start=8,
    tiles="CartoDB positron",
)

# Color by risk
def risk_color(risk):
    if risk >= 3.5:
        return "#c0392b"   # deep red – Gaza/Lebanon border
    elif risk >= 2.5:
        return "#e67e22"   # orange – elevated
    elif risk >= 1.8:
        return "#f1c40f"   # yellow – medium
    else:
        return "#27ae60"   # green – standard

# Draw road polylines
for name, wpts, risk, *_ in allocations:
    color = risk_color(risk)
    folium.PolyLine(
        locations=wpts,
        color=color,
        weight=3,
        opacity=0.55,
        tooltip=f"{name}  (סיכון ×{risk})",
    ).add_to(m)

# Cluster shelters
cluster = MarkerCluster(
    name="מיגוניות (400)",
    options={"maxClusterRadius": 40, "disableClusteringAtZoom": 13},
).add_to(m)

for lat, lon, road, risk in shelter_points:
    color = risk_color(risk)
    folium.CircleMarker(
        location=[lat, lon],
        radius=6,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        weight=1.5,
        popup=folium.Popup(f"<b>מיגונית</b><br>{road}<br>רמת סיכון: {risk:.1f}", max_width=220),
        tooltip=f"מיגונית – {road}",
    ).add_to(cluster)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = """
<div style="position:fixed; bottom:40px; right:20px; z-index:9999;
     background:white; padding:12px 18px; border-radius:8px;
     border:2px solid #aaa; font-family:Arial,sans-serif; font-size:13px;
     box-shadow:3px 3px 6px rgba(0,0,0,0.3); direction:rtl;">
  <b style="font-size:15px;">מיגוניות בכבישי ישראל</b><br><br>
  <span style="color:#c0392b;">&#9632;</span> סיכון גבוה מאוד – עוטף עזה / גבול לבנון<br>
  <span style="color:#e67e22;">&#9632;</span> סיכון גבוה – צפון / כבישי עוטף<br>
  <span style="color:#f1c40f;">&#9632;</span> סיכון בינוני<br>
  <span style="color:#27ae60;">&#9632;</span> סיכון רגיל<br><br>
  <b>סה"כ: 400 מיגוניות</b>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Title ─────────────────────────────────────────────────────────────────────
title_html = """
<div style="position:fixed; top:15px; left:50%; transform:translateX(-50%);
     z-index:9999; background:white; padding:10px 24px; border-radius:8px;
     border:2px solid #555; font-family:Arial,sans-serif; font-size:16px;
     font-weight:bold; direction:rtl; box-shadow:3px 3px 6px rgba(0,0,0,0.25);">
  מיפוי 400 מיגוניות לאורך כבישי ישראל — ריכוז גבוה באזורי סיכון
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

# Layer control
folium.LayerControl().add_to(m)

m.save(OUTPUT)
print(f"Map saved: {OUTPUT}")

# Print summary
print("\nShelters per road:")
for name, wpts, risk, length, score in sorted(allocations, key=lambda x: -x[2]):
    n = road_shelter_counts[name]
    print(f"  {n:3d}  {name}  (risk={risk})")
