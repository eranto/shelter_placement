"""
Re-rank road shelters by missile alert density (Oct 7 2023 – present).

Data sources:
  - Shelter locations:  shelter_points_traffic.pkl   (from road_shelters_traffic.py)
  - Alert counts:       /tmp/geocoded_cities.json    (Nominatim-geocoded Pikud HaOref areas)
  - Raw alerts:         /tmp/israel_alerts.csv       (github.com/dleshem/israel-alerts-data)

Algorithm:
  For each shelter node, sum the alert counts of every geocoded city/area
  whose centroid falls within RADIUS_KM kilometres. Shelters are then ranked
  from highest total nearby alerts to lowest.

Output:
  road_shelters_alert_ranked.html  — interactive Folium map
"""

import pickle, json, math
import folium
from folium.plugins import MarkerCluster

HERE    = "/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006"
CKPT    = f"{HERE}/shelter_points_traffic.pkl"
CITIES  = "/tmp/geocoded_cities.json"
OUT_HTML = f"{HERE}/road_shelters_alert_ranked.html"

RADIUS_KM = 15.0   # alert "catchment" radius per shelter

# ── Helpers ───────────────────────────────────────────────────────────────────
def seg_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(dlat**2 + dlon**2)

def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#F9CA24'
    return '#6AB04C'

# ── Load shelters ─────────────────────────────────────────────────────────────
shelter_points, final_max = pickle.load(open(CKPT, 'rb'))
print(f"Loaded {len(shelter_points)} shelter points (pre-dedup).")

# Deduplicate: same 2.5 km threshold as road_shelters_traffic.py
MIN_DIST_KM = 2.5
priority_sorted = sorted(shelter_points, key=lambda p: (p[3], p[2]), reverse=True)
kept = []
for pt in priority_sorted:
    if not any(seg_km(pt[:2], k[:2]) < MIN_DIST_KM for k in kept):
        kept.append(pt)
shelter_points = kept
print(f"After {MIN_DIST_KM} km dedup: {len(shelter_points)} shelters.")

# ── Load geocoded alert cities ────────────────────────────────────────────────
geo = json.load(open(CITIES))
alert_locations = [
    (float(v['lat']), float(v['lon']), v['alerts'], city)
    for city, v in geo.items()
    if v.get('lat') is not None
]
print(f"Geocoded cities: {len(alert_locations)}")
total_alerts_available = sum(v['alerts'] for v in geo.values() if v.get('lat'))
total_alerts_all       = sum(v['alerts'] for v in geo.values())
print(f"Alert coverage: {total_alerts_available:,} / {total_alerts_all:,} "
      f"({100*total_alerts_available/total_alerts_all:.1f}%)")

# ── Score each shelter: sum of alerts within RADIUS_KM ───────────────────────
print(f"\nScoring shelters (radius={RADIUS_KM} km)...")
scored = []
for lat, lon, risk, cw, rname in shelter_points:
    nearby = sum(
        alerts
        for clat, clon, alerts, _ in alert_locations
        if seg_km((lat, lon), (clat, clon)) <= RADIUS_KM
    )
    scored.append((lat, lon, risk, cw, rname, nearby))

scored.sort(key=lambda x: x[5], reverse=True)
total = len(scored)

print(f"Scored {total} shelters.")
print(f"\nTop 20 by alert density:")
print(f"  {'#':>4}  {'Road':>6}  {'Alerts':>8}  {'Risk':>5}  Location")
for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored[:20], 1):
    print(f"  {rank:4d}  {rname:>6}  {alerts:8,}  {risk:5.1f}  ({lat:.4f}, {lon:.4f})")

# ── Alert score colour scale ──────────────────────────────────────────────────
max_score = scored[0][5] if scored else 1

def alert_color(score):
    if score >= max_score * 0.7:  return '#D63031'   # red   — very high
    if score >= max_score * 0.4:  return '#E17055'   # orange
    if score >= max_score * 0.2:  return '#F9CA24'   # yellow
    if score >= max_score * 0.05: return '#00B894'   # teal
    return '#B2BEC3'                                   # grey  — low

def alert_radius(score):
    return max(4, min(11, int(score / max(max_score, 1) * 10) + 3))

# ── Build Folium map ──────────────────────────────────────────────────────────
print("\nGenerating HTML map...")
m = folium.Map(location=[31.5, 34.9], zoom_start=8, tiles="CartoDB positron")

# Alert city markers (small transparent circles for context)
alert_group = folium.FeatureGroup(name="אזורי התרעה (מיקומי ערים)", show=False)
for clat, clon, alerts, city in sorted(alert_locations, key=lambda x: -x[2])[:200]:
    folium.CircleMarker(
        location=[clat, clon],
        radius=max(3, min(10, int(alerts / 200))),
        color='#636E72', fill=True, fill_color='#636E72',
        fill_opacity=0.25, weight=0.5,
        tooltip=f"{city}: {alerts:,} התרעות",
    ).add_to(alert_group)
alert_group.add_to(m)

# Shelter markers — ranked by alerts
cluster = MarkerCluster(
    name=f"מיגוניות לפי עדיפות התרעות ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
).add_to(m)

for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored, 1):
    col = alert_color(alerts)
    r_px = alert_radius(alerts)
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
            f"<b>מיגונית #{rank} לפי התרעות</b><br>"
            f"כביש: {rname}<br>"
            f"התרעות בסביבה ({RADIUS_KM:.0f} ק\"מ): <b>{alerts:,}</b><br>"
            f"סיכון גיאוגרפי: {risk:.1f}<br>"
            f"נתיבים (משוקלל): {cw:.1f}"
            f"</div>",
            max_width=240),
        tooltip=f"#{rank} | כביש {rname} | {alerts:,} התרעות",
    ).add_to(cluster)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;
     line-height:1.8;">
  <b style="font-size:13px;">סדר פריסת מיגוניות לפי עצמת התרעות</b>
  <hr style="margin:6px 0">
  <b>צבע = מספר התרעות בסביבה ({RADIUS_KM:.0f} ק"מ)</b><br>
  <span style="color:#D63031">&#9679;</span> גבוה מאוד (מקסימום)<br>
  <span style="color:#E17055">&#9679;</span> גבוה<br>
  <span style="color:#F9CA24">&#9679;</span> בינוני<br>
  <span style="color:#00B894">&#9679;</span> נמוך<br>
  <span style="color:#B2BEC3">&#9679;</span> מינימלי
  <hr style="margin:6px 0">
  גודל = עצמת התרעות<br>
  מספר = עדיפות פריסה (#1 = ראשון)
  <hr style="margin:6px 0">
  <b>סה"כ: {total} מיגוניות | תקן 5 דקות</b><br>
  <span style="font-size:10px;color:#888;">
    נתוני התרעות: github.com/dleshem/israel-alerts-data<br>
    Oct 7 2023 – {__import__('datetime').date.today()}<br>
    כיסוי: {100*total_alerts_available/total_alerts_all:.0f}% מסך ההתרעות
  </span>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
m.save(OUT_HTML)
print(f"Saved: {OUT_HTML}")

# ── Summary by alert tier ─────────────────────────────────────────────────────
print("\n── Deployment tiers by alert score ──")
tiers = [
    ("גבוה מאוד", lambda s: s >= max_score * 0.7),
    ("גבוה",      lambda s: max_score * 0.4 <= s < max_score * 0.7),
    ("בינוני",    lambda s: max_score * 0.2 <= s < max_score * 0.4),
    ("נמוך",      lambda s: max_score * 0.05 <= s < max_score * 0.2),
    ("מינימלי",   lambda s: s < max_score * 0.05),
]
for label, pred in tiers:
    n = sum(1 for *_, s in scored if pred(s))
    print(f"  {label:12s}: {n:4d} shelters")
