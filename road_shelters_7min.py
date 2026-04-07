"""
Place road shelters (מיגוניות) along Israeli roads so that every rider
can reach a shelter in time.

Logic
-----
• Standard: 5 minutes on high-risk roads (risk ≥ 3.0), 7 minutes on all others
• Worst case: rider is exactly halfway between two shelters
  → max gap = 2 × (time_min/60) × speed_km/h
• Speed by road type / risk:
    Danger-border roads  (risk ≥ 4.0): 70 km/h  5 min → gap ≤  11.7 km
    High-risk roads      (risk ≥ 3.0): 80 km/h  5 min → gap ≤  13.3 km
    Arterial roads       (risk ≥ 2.0): 90 km/h  7 min → gap ≤  21.0 km
    Highways             (risk < 2.0): 110 km/h 7 min → gap ≤  25.7 km
"""

import numpy as np
import folium
from folium.plugins import MarkerCluster

np.random.seed(7)
OUTPUT = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_7min.html"

# ── Complete road network ──────────────────────────────────────────────────────
# (name, [(lat, lon), ...], risk_weight)
ROADS = [
    # ── Gaza envelope & south (risk 4 / 3.5) ──────────────────────────────
    ("כביש 232 (עוטף עזה)",
     [(31.416,34.291),(31.382,34.315),(31.354,34.336),
      (31.318,34.362),(31.275,34.398),(31.242,34.425)], 4.0),
    ("כביש 34 (נגב מערבי – עוטף)",
     [(31.680,34.558),(31.586,34.510),(31.490,34.476),
      (31.416,34.450),(31.360,34.430)], 3.5),
    ("כביש 35 (קרית גת – שדרות)",
     [(31.610,34.773),(31.551,34.703),(31.518,34.622),
      (31.476,34.547),(31.426,34.494)], 3.5),
    ("כביש 25 (נגב מרכזי)",
     [(31.264,34.798),(31.242,34.625),(31.220,34.430)], 3.0),
    # ── גבול לבנון – גליל עליון (risk 4.0) ─────────────────────────────────
    # Waypoints kept south of Lebanon border (~33.07–33.27 depending on longitude)
    ("כביש 99 (גליל עליון – גבול לבנון)",
     [(33.02,35.09),(33.05,35.19),(33.05,35.33),
      (33.08,35.44),(33.07,35.57),(33.07,35.69)], 4.0),
    ("כביש 978 / 899 (קו גבול לבנון)",
     [(33.05,35.09),(33.06,35.14),(33.08,35.18),
      (33.13,35.24),(33.14,35.31),(33.09,35.38),(33.07,35.42)], 4.0),
    ("כביש 89 (מעלות–ראש הנקרה)",
     [(32.980,35.045),(33.019,35.039),(33.050,35.025),(33.075,35.000)], 3.5),
    ("כביש 80 (עכו–מעלות–חרמון)",
     [(32.925,35.083),(33.010,35.143),(33.080,35.204)], 3.0),
    ("כביש 90 (עמק הירדן – צפון)",
     [(33.197,35.550),(32.970,35.490),(32.735,35.575),
      (32.500,35.535),(32.240,35.499)], 2.5),
    ("כביש 77 (עכו–נהריה)",
     [(32.925,35.083),(33.003,35.097),(33.017,35.100)], 2.0),

    # ── רמת הגולן (risk 3.0) ─────────────────────────────────────────────
    ("כביש 98 (גולן – גבול סוריה)",
     [(32.750,35.780),(32.900,35.750),(33.050,35.700),
      (33.150,35.660),(33.250,35.620)], 3.0),
    ("כביש 91 (גולן רוחבי – קצרין)",
     [(32.985,35.490),(32.990,35.593),(32.990,35.690),(32.960,35.780)], 2.5),
    ("כביש 87 (טבריה–גולן)",
     [(32.793,35.531),(32.850,35.600),(32.960,35.680)], 2.0),

    # ── כביש 90 (בקעת הירדן – ים המלח – ערבה) ─────────────────────────
    ("כביש 90 (בקעת הירדן – ים המלח)",
     [(32.240,35.499),(32.000,35.488),(31.780,35.430),
      (31.550,35.436),(31.270,35.450),(30.980,35.434)], 2.5),
    ("כביש 90 (ערבה – אילת)",
     [(30.980,35.434),(30.600,35.250),(30.200,35.100),(29.558,34.948)], 2.0),

    # ── כביש 40 (ניצנה – מצפה רמון – אילת) ──────────────────────────────
    ("כביש 40 (ניצנה–מצפה רמון–אילת)",
     [(30.870,34.430),(30.605,34.803),(30.380,34.880),
      (30.200,34.950),(29.870,35.022),(29.558,34.948)], 2.0),
    ("כביש 40 (באר שבע–אשקלון)",
     [(31.680,34.558),(31.556,34.600),(31.435,34.647),(31.270,34.797)], 2.5),

    # ── כביש 6 (חוצה ישראל) ─────────────────────────────────────────────
    ("כביש 6 (חוצה ישראל – מרכז–צפון)",
     [(32.080,34.930),(32.200,34.988),(32.350,35.003),
      (32.500,35.012),(32.650,35.058),(32.800,35.097),(32.870,35.100)], 1.5),
    ("כביש 6 (חוצה ישראל – דרום)",
     [(31.700,34.750),(31.850,34.798),(32.000,34.870),(32.080,34.930)], 1.5),

    # ── כביש 1 (ת"א–ירושלים) ─────────────────────────────────────────────
    ("כביש 1 (תל אביב–ירושלים)",
     [(32.082,34.781),(31.975,34.908),(31.905,34.987),
      (31.850,35.065),(31.793,35.172),(31.782,35.216)], 1.8),
    ("כביש 443 (מודיעין–ירושלים)",
     [(31.895,35.010),(31.855,35.075),(31.822,35.143),(31.800,35.210)], 1.8),

    # ── כביש 2 (חוף – גוש דן–חיפה–עכו) ──────────────────────────────────
    ("כביש 2 (גוש דן–חדרה–חיפה)",
     [(32.082,34.781),(32.175,34.832),(32.320,34.870),
      (32.460,34.924),(32.620,34.961),(32.820,34.981),(32.920,35.012)], 1.4),

    # ── כביש 4 (חוף – גוש דן–אשדוד–אשקלון) ──────────────────────────────
    ("כביש 4 (גוש דן–אשדוד–אשקלון)",
     [(32.082,34.781),(31.985,34.750),(31.870,34.715),
      (31.760,34.660),(31.680,34.583)], 2.0),

    # ── כביש 3 + 38 (שפלה – ירושלים) ────────────────────────────────────
    ("כביש 3 (שפלה – לוד–ירושלים)",
     [(31.990,34.892),(31.900,34.900),(31.869,34.904),(31.820,35.050)], 1.3),
    ("כביש 38 (בית שמש–ירושלים)",
     [(31.780,35.214),(31.733,35.005),(31.697,34.990)], 1.3),

    # ── כבישי צפון (כרמל, עמקים, גליל) ────────────────────────────────
    ("כביש 85 (עכו–שפרעם–טבריה)",
     [(32.925,35.083),(32.874,35.156),(32.845,35.258),
      (32.808,35.388),(32.770,35.491)], 2.0),
    ("כביש 65 (וואדי ערה – מגידו–עפולה)",
     [(32.562,35.185),(32.517,35.104),(32.487,35.001),(32.461,34.942)], 1.8),
    ("כביש 70 (חיפה–זכרון–חדרה)",
     [(32.820,34.981),(32.720,34.960),(32.620,34.944),(32.500,34.918)], 1.4),
    ("כביש 75 / 79 (נצרת–עפולה–טבריה)",
     [(32.700,35.303),(32.650,35.225),(32.606,35.188),
      (32.590,35.109),(32.562,35.050)], 1.4),
    ("כביש 60 (ירושלים–רמאללה–שכם, קטע ישראלי)",
     [(31.782,35.216),(31.870,35.220),(31.970,35.240),(32.120,35.260)], 1.8),

    # ── כביש 31 + 25 (נגב מרכזי) ─────────────────────────────────────────
    ("כביש 31 (באר שבע–ערד–מצדה)",
     [(31.270,34.797),(31.267,35.000),(31.262,35.210),(31.190,35.344)], 1.8),
    ("כביש 25 / 204 (נגב דרום-מערב)",
     [(31.264,34.798),(31.100,34.650),(30.900,34.600),(30.700,34.550)], 2.5),

    # ── כביש 5 + 57 (מרכז–שרון–שומרון) ─────────────────────────────────
    ("כביש 5 (אריאל–פ\"ת–גוש דן)",
     [(32.082,34.810),(32.082,34.950),(32.082,35.030),(32.100,35.105)], 1.5),
    ("כביש 57 (נתניה–טולכרם–בקעה)",
     [(32.320,34.870),(32.310,34.990),(32.295,35.090)], 1.5),

    # ── כביש 22 + כרמל ────────────────────────────────────────────────────
    ("כביש 22 (נשר–חיפה–קרית אתא)",
     [(32.820,34.981),(32.830,35.020),(32.820,35.068),(32.806,35.096)], 1.3),

    # ── כביש 96 (קרית שמונה – חרמון) ─────────────────────────────────────
    ("כביש 96 (קרית שמונה–דן–שניר)",
     [(33.197,35.550),(33.230,35.564),(33.250,35.580)], 3.0),
]

# ── Geometry helpers ───────────────────────────────────────────────────────────

def seg_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * np.cos(np.radians((p1[0]+p2[0])/2))
    return np.sqrt(dlat**2 + dlon**2)

def road_length_km(wpts):
    return sum(seg_km(wpts[i], wpts[i+1]) for i in range(len(wpts)-1))

def interpolate_km(wpts, spacing_km):
    """
    Return list of (lat, lon) placed every spacing_km along the polyline,
    always including the start and end points.
    """
    pts = []
    # Build cumulative distance table
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total == 0:
        return [wpts[0], wpts[-1]]

    # Sample at multiples of spacing_km
    distances = [0.0]
    d = spacing_km
    while d < total:
        distances.append(d)
        d += spacing_km
    distances.append(total)
    distances = sorted(set(distances))

    for target in distances:
        # find segment
        seg = np.searchsorted(cum, target, side='right') - 1
        seg = min(seg, len(wpts)-2)
        seg_start = cum[seg]
        seg_len   = cum[seg+1] - seg_start
        if seg_len == 0:
            pts.append(wpts[seg])
        else:
            t = (target - seg_start) / seg_len
            lat = wpts[seg][0] + t*(wpts[seg+1][0]-wpts[seg][0])
            lon = wpts[seg][1] + t*(wpts[seg+1][1]-wpts[seg][1])
            pts.append((lat, lon))
    return pts

def speed_kmh(risk):
    if risk >= 4.0: return 70
    if risk >= 3.0: return 80
    if risk >= 2.0: return 90
    return 110

def time_min(risk):
    """5 minutes for all roads."""
    return 5

def max_gap_km(risk):
    """Max allowed gap = 2 × (time_min/60 × speed) so midpoint is within time_min."""
    return 2 * (time_min(risk) / 60) * speed_kmh(risk)

# ── Place shelters ────────────────────────────────────────────────────────────

shelter_points = []   # (lat, lon, road_name, risk)
road_stats = []

for name, wpts, risk in ROADS:
    km      = road_length_km(wpts)
    gap     = max_gap_km(risk)
    spacing = gap          # place shelters at the max allowed spacing
    pts     = interpolate_km(wpts, spacing)
    # small random perpendicular jitter (realistic: shelter is a few m off road)
    jittered = []
    for lat, lon in pts:
        jlat = lat + np.random.uniform(-0.0005, 0.0005)
        jlon = lon + np.random.uniform(-0.0007, 0.0007)
        jittered.append((jlat, jlon, name, risk))
    shelter_points.extend(jittered)
    road_stats.append((name, km, speed_kmh(risk), time_min(risk), gap, len(pts), risk))

total = len(shelter_points)
print(f"Total shelters for 7-min coverage: {total}")
print(f"Total mapped road network: {sum(r[1] for r in road_stats):.0f} km\n")

# ── Color helpers ──────────────────────────────────────────────────────────────

def risk_color(risk):
    if risk >= 4.0: return "#c0392b"
    if risk >= 3.0: return "#e67e22"
    if risk >= 2.0: return "#f1c40f"
    return "#27ae60"

def risk_label(risk):
    if risk >= 4.0: return "גבוה מאוד – גבול לבנון/עזה"
    if risk >= 3.0: return "גבוה"
    if risk >= 2.0: return "בינוני"
    return "רגיל"

# ── Build Folium map ───────────────────────────────────────────────────────────

m = folium.Map(location=[31.5, 35.0], zoom_start=8, tiles="CartoDB positron")

# --- Draw roads ---
for name, wpts, risk in ROADS:
    folium.PolyLine(
        locations=wpts,
        color=risk_color(risk),
        weight=3.5,
        opacity=0.5,
        tooltip=f"{name}  |  סיכון: {risk_label(risk)}",
    ).add_to(m)

# --- Draw coverage circles (light, behind shelters) ---
circle_group = folium.FeatureGroup(name="טווח כיסוי (5 דקות)", show=False)
for lat, lon, road, risk in shelter_points:
    spd  = speed_kmh(risk)
    r_km = (time_min(risk) / 60) * spd   # km in allowed time
    r_m  = r_km * 1000
    folium.Circle(
        location=[lat, lon],
        radius=r_m,
        color=risk_color(risk),
        fill=True,
        fill_color=risk_color(risk),
        fill_opacity=0.04,
        weight=0.4,
        opacity=0.25,
    ).add_to(circle_group)
circle_group.add_to(m)

# --- Shelter markers ---
cluster = MarkerCluster(
    name=f"מיגוניות ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
).add_to(m)

for lat, lon, road, risk in shelter_points:
    spd  = speed_kmh(risk)
    tmin = time_min(risk)
    r_km = (tmin / 60) * spd
    folium.CircleMarker(
        location=[lat, lon],
        radius=6,
        color="white",
        fill=True,
        fill_color=risk_color(risk),
        fill_opacity=0.9,
        weight=1.5,
        popup=folium.Popup(
            f"<div style='direction:rtl;font-family:Arial'>"
            f"<b>מיגונית</b><br>"
            f"כביש: {road}<br>"
            f"רמת סיכון: {risk_label(risk)}<br>"
            f"תקן: {tmin} דקות<br>"
            f"מהירות הנחה: {spd} קמ\"ש<br>"
            f"רדיוס כיסוי: {r_km:.1f} ק\"מ"
            f"</div>",
            max_width=250,
        ),
        tooltip=f"מיגונית – {road}",
    ).add_to(cluster)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #888;font-family:Arial,sans-serif;font-size:13px;
     box-shadow:3px 3px 8px rgba(0,0,0,0.3);direction:rtl;min-width:290px;">
  <b style="font-size:15px;">מיגוניות בכבישי ישראל — תקן 5 דקות</b>
  <hr style="margin:8px 0">
  <span style="color:#c0392b;font-size:16px;">&#9632;</span>
    סיכון גבוה מאוד — גבול לבנון / עוטף עזה<br>
    &nbsp;&nbsp;&nbsp;70 קמ&quot;ש | רדיוס: 5.8 ק&quot;מ<br><br>
  <span style="color:#e67e22;font-size:16px;">&#9632;</span>
    סיכון גבוה — 80 קמ&quot;ש | רדיוס: 6.7 ק&quot;מ<br><br>
  <span style="color:#f1c40f;font-size:16px;">&#9632;</span>
    סיכון בינוני — 90 קמ&quot;ש | רדיוס: 7.5 ק&quot;מ<br><br>
  <span style="color:#27ae60;font-size:16px;">&#9632;</span>
    סיכון רגיל — 110 קמ&quot;ש | רדיוס: 9.2 ק&quot;מ<br>
  <hr style="margin:8px 0">
  <b>סה&quot;כ מיגוניות: {total}</b><br>
  <b>כבישים ממופים: {sum(r[1] for r in road_stats):.0f} ק&quot;מ</b><br>
  <small>תקן אחיד: כל נהג/ת מגיע/ה למיגונית תוך 5 דקות</small>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Title ─────────────────────────────────────────────────────────────────────
title_html = f"""
<div style="position:fixed;top:15px;left:50%;transform:translateX(-50%);
     z-index:9999;background:white;padding:10px 28px;border-radius:10px;
     border:2px solid #555;font-family:Arial,sans-serif;font-size:16px;
     font-weight:bold;direction:rtl;box-shadow:3px 3px 8px rgba(0,0,0,0.25);">
  מיפוי {total} מיגוניות לכיסוי מלא בכבישי ישראל — הגעה תוך 5 דקות
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUTPUT)
print(f"\nMap saved: {OUTPUT}")

# ── Print per-road summary ─────────────────────────────────────────────────────
print(f"\n{'Road':<48} {'km':>6} {'spd':>5} {'min':>4} {'gap':>7} {'n':>5}")
print("─"*82)
for name, km, spd, tmin, gap, n, risk in sorted(road_stats, key=lambda x: -x[6]):
    print(f"{name:<48} {km:6.1f} {spd:5.0f} {tmin:4.0f} {gap:7.1f} {n:5d}")
print("─"*82)
total_km  = sum(r[1] for r in road_stats)
total_n   = sum(r[5] for r in road_stats)
hi_risk   = [(r) for r in road_stats if r[6] >= 3.0]
lo_risk   = [(r) for r in road_stats if r[6] <  3.0]
print(f"{'TOTAL':<48} {total_km:6.0f} {'':>17} {total_n:5d}")
print(f"\n── By tier ──")
print(f"  High-risk (≥3.0, 5-min standard): {sum(r[1] for r in hi_risk):6.0f} km  →  {sum(r[5] for r in hi_risk):4d} shelters")
print(f"  Regular   (<3.0, 7-min standard): {sum(r[1] for r in lo_risk):6.0f} km  →  {sum(r[5] for r in lo_risk):4d} shelters")
print(f"  TOTAL:                            {total_km:6.0f} km  →  {total_n:4d} shelters")
