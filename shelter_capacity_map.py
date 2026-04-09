"""
Generate an interactive map of shelters.

Color = composite risk score (0–1):
  Blue-grey (#74B9FF) — very low   (score < 0.08)
  Green     (#00B894) — low        (0.08 – 0.16)
  Yellow    (#FDCB6E) — medium     (0.16 – 0.28)
  Orange    (#E17055) — high       (0.28 – 0.40)
  Red       (#D63031) — very high  (≥ 0.40)

Size = suggested capacity (larger = bigger shelter needed).

Input:  shelters_final_placements.csv
Output: shelters_map.html
"""

import csv, folium
from folium.plugins import MarkerCluster
from pathlib import Path
from collections import Counter

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── Load data ─────────────────────────────────────────────────────────────────
rows = []
with open(HERE / "shelters_final_placements.csv", newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
print(f"Loaded {len(rows)} shelters.")

# ── Risk-score color encoding ─────────────────────────────────────────────────
RISK_BINS = [
    (0.08, '#74B9FF', 'Very low  (< 0.08)'),
    (0.16, '#00B894', 'Low       (0.08 – 0.16)'),
    (0.28, '#FDCB6E', 'Medium    (0.16 – 0.28)'),
    (0.40, '#E17055', 'High      (0.28 – 0.40)'),
    (1.00, '#D63031', 'Very high (≥ 0.40)'),
]

def risk_color(score):
    for threshold, color, _ in RISK_BINS:
        if score < threshold:
            return color
    return RISK_BINS[-1][1]

# ── Capacity → marker radius ──────────────────────────────────────────────────
CAP_RADIUS = {6: 5, 12: 7, 20: 10}

def cap_radius(cap):
    return CAP_RADIUS.get(int(cap), 7)

# ── Zone label ────────────────────────────────────────────────────────────────
ZONE_LABEL = {'north': 'North border', 'gaza': 'Gaza envelope', 'standard': 'Standard'}

# ── Build map ─────────────────────────────────────────────────────────────────
m = folium.Map(location=[31.8, 35.0], zoom_start=8, tiles="CartoDB positron")

cluster = MarkerCluster(
    name=f"Shelters by risk score ({len(rows)})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12}
).add_to(m)

for r in rows:
    lat   = float(r['lat'])
    lon   = float(r['lon'])
    score = float(r['composite_score'])
    cap   = int(r['suggested_capacity'])
    rank  = r['rank']
    road  = r['road']
    zone  = r.get('zone', '')
    aadt_n   = int(r['aadt_normal'])
    aadt_w   = int(r['aadt_wartime'])
    people   = float(r['estimated_people_in_catchment'])
    speed    = r['road_speed_kmh']
    catch    = r['catchment_per_dir_km']
    alerts   = int(r['nearby_alerts_marapr2026']) if r.get('nearby_alerts_marapr2026') else 0
    alert_sec = r.get('alert_seconds', '')

    alert_win_html = (
        f"Alert window: <b>{int(alert_sec) // 60} min</b> "
        f"({'near-border' if int(alert_sec) == 240 else 'standard'})<br>"
        if alert_sec else ""
    )

    popup_html = (
        f"<div style='font-family:Arial;font-size:13px;min-width:240px'>"
        f"<b>Shelter #{rank}</b><br>"
        f"Road: {road} &nbsp;|&nbsp; Zone: {zone}<br>"
        f"<hr style='margin:5px 0'>"
        f"<b>Risk score: {score:.3f}</b><br>"
        f"Nearby alerts Mar–Apr 2026: {alerts:,}<br>"
        f"{alert_win_html}"
        f"<hr style='margin:5px 0'>"
        f"<b>Capacity: {cap} people</b><br>"
        f"Est. people in catchment: {people:.1f}<br>"
        f"Catchment per direction: {catch} km<br>"
        f"Road speed: {speed} km/h<br>"
        f"<hr style='margin:5px 0'>"
        f"AADT (normal): {aadt_n:,} vehicles/day<br>"
        f"AADT (wartime 10%): {aadt_w:,} vehicles/day<br>"
        f"</div>"
    )

    folium.CircleMarker(
        location=[lat, lon],
        radius=cap_radius(cap),
        color='white',
        fill=True,
        fill_color=risk_color(score),
        fill_opacity=0.9,
        weight=1.2,
        popup=folium.Popup(popup_html, max_width=290),
        tooltip=f"#{rank} | {road} | Risk: {score:.3f} | Cap: {cap} | Alerts: {alerts:,}",
    ).add_to(cluster)

# ── Legend ────────────────────────────────────────────────────────────────────
risk_bin_counts = Counter()
for r in rows:
    score = float(r['composite_score'])
    for threshold, color, label in RISK_BINS:
        if score < threshold:
            risk_bin_counts[label] += 1
            break

legend_html = """
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;line-height:1.9;">
  <b style="font-size:13px;">Risk Score</b>
  <hr style="margin:6px 0">
  <span style="font-size:10px;color:#666">composite = 0.6×alerts + 0.4×border proximity</span>
  <hr style="margin:6px 0">
""" + "".join(
    f"  <span style='color:{color}'>&#9679;</span> "
    f"{label} &nbsp;<span style='color:#888'>({risk_bin_counts.get(label,0)})</span><br>"
    for _, color, label in RISK_BINS
) + f"""
  <hr style="margin:6px 0">
  <b style="font-size:11px;">Marker size = capacity</b><br>
  <span style="font-size:10px;color:#888">
    &#9679; 6p &nbsp; &#9679; 12p &nbsp; &#9679; 20p
  </span>
  <hr style="margin:6px 0">
  <span style="font-size:10px;color:#888">
    Alert window: 4 min (≤15 km from border) | 5 min (other)<br>
    Total: {len(rows)} shelters
  </span>
</div>"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)

out = HERE / "shelters_map.html"
m.save(str(out))
print(f"Saved: {out.name}")
