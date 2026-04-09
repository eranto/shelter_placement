"""
Generate an interactive map of shelters colored and sized by suggested capacity.

Color legend:
  Grey   (#B2BEC3) — 6 people  (low-traffic rural road)
  Green  (#00B894) — 12 people
  Orange (#E17055) — 20 people
  Red    (#D63031) — 30 people
  Dark   (#2D3436) — 50 people  (capped, may be undersized)

Input:  shelters_final_placements.csv
Output: shelters_capacity_map.html
"""

import csv, folium
from folium.plugins import MarkerCluster
from pathlib import Path

HERE = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")

# ── Load data ─────────────────────────────────────────────────────────────────
rows = []
with open(HERE / "shelters_final_placements.csv", newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
print(f"Loaded {len(rows)} shelters.")

# ── Visual encoding ───────────────────────────────────────────────────────────
CAP_COLOR = {
     6: '#B2BEC3',   # grey
    12: '#00B894',   # green
    20: '#F9CA24',   # yellow
    30: '#E17055',   # orange
    50: '#D63031',   # red
}
CAP_RADIUS = {6: 5, 12: 6, 20: 8, 30: 10, 50: 13}

def cap_color(cap):
    return CAP_COLOR.get(int(cap), '#636E72')

def cap_radius(cap):
    return CAP_RADIUS.get(int(cap), 7)

# ── Zone label ────────────────────────────────────────────────────────────────
ZONE_LABEL = {'north': 'North border', 'gaza': 'Gaza envelope', 'standard': 'Standard'}

# ── Build map ─────────────────────────────────────────────────────────────────
m = folium.Map(location=[31.8, 35.0], zoom_start=8, tiles="CartoDB positron")

cluster = MarkerCluster(
    name=f"Shelters with capacity ({len(rows)})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12}
).add_to(m)

for r in rows:
    lat  = float(r['lat'])
    lon  = float(r['lon'])
    cap  = int(r['suggested_capacity'])
    rank = r['rank']
    road = r['road']
    zone = ZONE_LABEL.get(r['zone'], r['zone'])
    aadt_n    = int(r['aadt_normal'])
    aadt_w    = int(r['aadt_wartime'])
    people    = float(r['estimated_people_in_catchment'])
    speed     = r['road_speed_kmh']
    catch     = r['catchment_per_dir_km']
    alerts    = int(r['nearby_alerts_marapr2026']) if r.get('nearby_alerts_marapr2026') else 0
    base_cap  = int(r['base_capacity'])
    upgraded  = r.get('capacity_upgraded', 'no') == 'yes'
    reason    = r.get('upgrade_reason', '')

    upgrade_html = (
        f"<span style='color:#E17055'>&#9650; upgraded from {base_cap} &nbsp;<i>({reason})</i></span><br>"
        if upgraded else ""
    )

    popup_html = (
        f"<div style='font-family:Arial;font-size:13px;min-width:240px'>"
        f"<b>Shelter #{rank}</b><br>"
        f"Road: {road} &nbsp;|&nbsp; Zone: {zone}<br>"
        f"<hr style='margin:5px 0'>"
        f"<b>Capacity: {cap} people</b><br>"
        f"{upgrade_html}"
        f"Est. people in catchment: {people:.1f}<br>"
        f"Catchment per direction: {catch} km<br>"
        f"Road speed: {speed} km/h<br>"
        f"<hr style='margin:5px 0'>"
        f"AADT (normal): {aadt_n:,} vehicles/day<br>"
        f"AADT (wartime 10%): {aadt_w:,} vehicles/day<br>"
        f"Nearby alerts Mar–Apr 2026: {alerts:,}<br>"
        f"</div>"
    )

    folium.CircleMarker(
        location=[lat, lon],
        radius=cap_radius(cap),
        color='white',
        fill=True,
        fill_color=cap_color(cap),
        fill_opacity=0.9,
        weight=1.2,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"#{rank} | {road} | Capacity: {cap} | Wartime AADT: {aadt_w:,}",
    ).add_to(cluster)

# ── Legend ────────────────────────────────────────────────────────────────────
from collections import Counter
cap_counts = Counter(int(r['suggested_capacity']) for r in rows)

legend_html = """
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;line-height:1.9;">
  <b style="font-size:13px;">Shelter Capacity</b>
  <hr style="margin:6px 0">
  <b>Wartime traffic = 10% of normal AADT</b><br>
  Peak hour · 90-sec alert · 1.3 people/vehicle
  <hr style="margin:6px 0">
""" + "".join(
    f"  <span style='color:{CAP_COLOR[cap]}'>&#9679;</span> "
    f"{cap} people &nbsp;<span style='color:#888'>({cap_counts.get(cap,0)})</span><br>"
    for cap in [6, 12, 20, 30, 50]
) + f"""
  <hr style="margin:6px 0">
  <span style="font-size:10px;color:#888">Total: {len(rows)} shelters</span>
</div>"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)

out = HERE / "shelters_map.html"
m.save(str(out))
print(f"Saved: {out.name}")
