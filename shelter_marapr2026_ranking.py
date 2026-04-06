"""
Re-rank road shelters by missile alert density for March–April 2026 only.

Changes vs shelter_alert_ranking.py:
  1. Alert counts restricted to 2026-03 and 2026-04
  2. Deduplication: shelters within MIN_DIST_KM of each other are merged
     (keep the one on the higher-capacity / higher-risk road)
  3. Northern coverage check: ensure key border towns have at least one
     shelter within NORTH_RADIUS_KM; inject road-side sentinels if missing

Output:
  shelters_marapr2026_alert_ranked.html
  shelters_marapr2026_deduped.csv
"""

import csv, json, math, pickle, datetime
from pathlib import Path
import folium
from folium.plugins import MarkerCluster

HERE      = Path("/Users/erantoch/My Drive (erantoch@gmail.com)/Public Work/code/Shelter Placement 2006")
CKPT      = HERE / "shelter_points_traffic.pkl"
ALERTS_CSV = "/tmp/israel_alerts.csv"
GEO_FILE  = "/tmp/geocoded_cities.json"
OUT_HTML  = HERE / "shelters_marapr2026_alert_ranked.html"
OUT_CSV   = HERE / "shelters_marapr2026_deduped.csv"

RADIUS_KM   = 15.0   # alert catchment radius
MIN_DIST_KM = 2.5    # minimum distance between any two shelters (matches road_shelters_traffic.py)
NORTH_RADIUS_KM = 20.0  # coverage radius for northern sentinel check

TARGET_MONTHS = {'2026-03', '2026-04'}

# ── Helpers ───────────────────────────────────────────────────────────────────
def dist_km(p1, p2):
    dlat = (p2[0] - p1[0]) * 111.0
    dlon = (p2[1] - p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

# ── 1. Build Mar–Apr 2026 alert counts ───────────────────────────────────────
print("Counting Mar–Apr 2026 alerts...")
city_counts = {}
with open(ALERTS_CSV, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('alertDate', '')[:7] not in TARGET_MONTHS:
            continue
        for area in row.get('data', '').split(','):
            base = area.strip()
            if ' - ' in base:
                base = base.split(' - ')[0].strip()
            if base:
                city_counts[base] = city_counts.get(base, 0) + 1

total_raw = sum(city_counts.values())
print(f"  {len(city_counts)} unique areas, {total_raw:,} alert-area instances")

# ── 2. Attach geocoordinates ──────────────────────────────────────────────────
geo_db = json.load(open(GEO_FILE))
# Build name→coords lookup from geocoded_cities
coords_map = {city: (float(v['lat']), float(v['lon']))
              for city, v in geo_db.items() if v.get('lat')}

alert_locations = []
covered = 0
for city, cnt in city_counts.items():
    if city in coords_map:
        lat, lon = coords_map[city]
        alert_locations.append((lat, lon, cnt, city))
        covered += cnt

print(f"  Geocoded coverage: {covered:,}/{total_raw:,} ({100*covered/total_raw:.1f}%)")

# ── 3. Load shelters ──────────────────────────────────────────────────────────
shelter_points, final_max = pickle.load(open(CKPT, 'rb'))
print(f"\nLoaded {len(shelter_points)} shelter points.")

# ── 4. Deduplicate shelters (min distance MIN_DIST_KM) ───────────────────────
# Priority: higher cap_w first, then higher risk
priority_sorted = sorted(shelter_points,
                         key=lambda p: (p[3], p[2]),   # (cap_w, risk) desc
                         reverse=True)

kept = []
for pt in priority_sorted:
    lat, lon = pt[0], pt[1]
    too_close = any(dist_km((lat, lon), (k[0], k[1])) < MIN_DIST_KM for k in kept)
    if not too_close:
        kept.append(pt)

print(f"After dedup ({MIN_DIST_KM} km min): {len(kept)} shelters "
      f"(removed {len(shelter_points)-len(kept)})")

# ── 5. Northern coverage check ────────────────────────────────────────────────
# Key northern towns that must be covered
NORTH_TOWNS = {
    'קריית שמונה':  (33.2075, 35.5706),
    'מטולה':        (33.2817, 35.5706),
    'נהריה':        (33.0044, 35.0936),
    'עכו':          (32.9228, 35.0683),
    'צפת':          (32.9647, 35.4956),
    'מנרה':         (33.2239, 35.5228),
    'שלומי':        (33.0722, 35.1472),
    'כרמיאל':       (32.9078, 35.2975),
    'מעלות תרשיחא': (33.0172, 35.2744),
}

# Sentinel shelters to inject when a northern town lacks nearby coverage
# (placed on the nearest main road to the town)
NORTH_SENTINELS = {
    'קריית שמונה':  (33.2075, 35.5706, 4.0, 2.0, '90'),
    'מטולה':        (33.2817, 35.5706, 4.0, 1.5, '90'),
    'מנרה':         (33.2239, 35.5228, 4.0, 1.5, '899'),
    'שלומי':        (33.0722, 35.1472, 4.0, 1.5, '70'),
    'נהריה':        (33.0044, 35.0936, 3.5, 2.0, '4'),
    'עכו':          (32.9228, 35.0683, 3.5, 2.0, '4'),
    'צפת':          (32.9647, 35.4956, 3.5, 1.5, '89'),
    'כרמיאל':       (32.9078, 35.2975, 3.0, 2.0, '85'),
    'מעלות תרשיחא': (33.0172, 35.2744, 3.5, 1.5, '89'),
}

injected = []
for town, (tlat, tlon) in NORTH_TOWNS.items():
    nearest = min((dist_km((tlat, tlon), (k[0], k[1])) for k in kept), default=999)
    if nearest > NORTH_RADIUS_KM:
        s = NORTH_SENTINELS[town]
        kept.append(s)
        injected.append((town, s, nearest))
        print(f"  ⚠ {town}: nearest shelter was {nearest:.1f} km — injected sentinel on road {s[4]}")
    else:
        pass  # covered

if not injected:
    print("  Northern coverage OK — all towns have a shelter within "
          f"{NORTH_RADIUS_KM:.0f} km.")
else:
    print(f"  Injected {len(injected)} northern sentinels → total: {len(kept)}")

# ── 6. Score each shelter: Mar–Apr 2026 alerts within RADIUS_KM ───────────────
print(f"\nScoring {len(kept)} shelters (radius={RADIUS_KM} km, Mar–Apr 2026)...")
scored = []
for lat, lon, risk, cw, rname in kept:
    nearby = sum(
        cnt for clat, clon, cnt, _ in alert_locations
        if dist_km((lat, lon), (clat, clon)) <= RADIUS_KM
    )
    scored.append((lat, lon, risk, cw, rname, nearby))

scored.sort(key=lambda x: x[5], reverse=True)
total = len(scored)
max_score = scored[0][5] if scored else 1

print(f"\nTop 20 by Mar–Apr 2026 alert density:")
print(f"  {'#':>4}  {'Road':>6}  {'Alerts':>8}  {'Risk':>5}  Location")
for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored[:20], 1):
    print(f"  {rank:4d}  {rname:>6}  {alerts:8,}  {risk:5.1f}  ({lat:.4f},{lon:.4f})")

# ── 7. Colour helpers ─────────────────────────────────────────────────────────
def alert_color(score):
    if score >= max_score * 0.7:  return '#D63031'
    if score >= max_score * 0.4:  return '#E17055'
    if score >= max_score * 0.2:  return '#F9CA24'
    if score >= max_score * 0.05: return '#00B894'
    return '#B2BEC3'

def alert_radius(score):
    return max(4, min(11, int(score / max(max_score, 1) * 10) + 3))

# ── 8. Folium map ─────────────────────────────────────────────────────────────
print("\nGenerating HTML map...")
m = folium.Map(location=[32.0, 35.0], zoom_start=8, tiles="CartoDB positron")

# Alert city dots (top 300)
alert_group = folium.FeatureGroup(name="אזורי התרעה מר-אפר 2026", show=False)
for clat, clon, cnt, city in sorted(alert_locations, key=lambda x: -x[2])[:300]:
    folium.CircleMarker(
        location=[clat, clon],
        radius=max(3, min(12, int(cnt / 50))),
        color='#636E72', fill=True, fill_color='#636E72',
        fill_opacity=0.25, weight=0.5,
        tooltip=f"{city}: {cnt:,} התרעות (מר-אפר 2026)",
    ).add_to(alert_group)
alert_group.add_to(m)

# Injected northern sentinels layer
if injected:
    north_group = folium.FeatureGroup(name="מיגוניות צפון (חיזוק)", show=True)
    for town, s, prev_dist in injected:
        lat, lon, risk, cw, rname = s
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color='blue', icon='star', prefix='fa'),
            tooltip=f"חיזוק צפון: {town} | כביש {rname}",
            popup=folium.Popup(
                f"<div dir='rtl'><b>מיגונית חיזוק צפון</b><br>"
                f"עיר: {town}<br>כביש: {rname}<br>"
                f"(הוספה מכיוון שהמיגונית הקרובה הייתה {prev_dist:.1f} ק\"מ)</div>",
                max_width=220),
        ).add_to(north_group)
    north_group.add_to(m)

# Shelter cluster
cluster = MarkerCluster(
    name=f"מיגוניות מר-אפר 2026 ({total})",
    options={"maxClusterRadius": 35, "disableClusteringAtZoom": 12},
).add_to(m)

for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored, 1):
    col = alert_color(alerts)
    r_px = alert_radius(alerts)
    folium.CircleMarker(
        location=[lat, lon],
        radius=r_px,
        color='white', fill=True, fill_color=col,
        fill_opacity=0.92, weight=1.0,
        popup=folium.Popup(
            f"<div dir='rtl' style='font-family:Arial;font-size:13px;'>"
            f"<b>מיגונית #{rank}</b><br>"
            f"כביש: {rname}<br>"
            f"התרעות מר-אפר 2026 ({RADIUS_KM:.0f} ק\"מ): <b>{alerts:,}</b><br>"
            f"סיכון גיאוגרפי: {risk:.1f}<br>נתיבים: {cw:.1f}"
            f"</div>", max_width=240),
        tooltip=f"#{rank} | כביש {rname} | {alerts:,} התרעות מר-אפר 2026",
    ).add_to(cluster)

# Legend
legend_html = f"""
<div style="position:fixed;bottom:40px;right:20px;z-index:9999;
     background:white;padding:14px 20px;border-radius:10px;
     border:2px solid #aaa;font-family:Arial;font-size:12px;direction:rtl;
     line-height:1.8;">
  <b style="font-size:13px;">עדיפות מיגוניות — מרץ-אפריל 2026</b>
  <hr style="margin:6px 0">
  <b>צבע = התרעות בסביבה ({RADIUS_KM:.0f} ק"מ)</b><br>
  <span style="color:#D63031">&#9679;</span> גבוה מאוד<br>
  <span style="color:#E17055">&#9679;</span> גבוה<br>
  <span style="color:#F9CA24">&#9679;</span> בינוני<br>
  <span style="color:#00B894">&#9679;</span> נמוך<br>
  <span style="color:#B2BEC3">&#9679;</span> מינימלי
  <hr style="margin:6px 0">
  סה"כ: {total} מיגוניות<br>
  מרחק מינימלי: {MIN_DIST_KM} ק"מ<br>
  <span style="font-size:10px;color:#888;">
    התרעות: מרץ-אפריל 2026 בלבד<br>
    כיסוי: {100*covered/total_raw:.0f}% מסך ההתרעות
  </span>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)
m.save(str(OUT_HTML))
print(f"Saved: {OUT_HTML.name}")

# ── 9. Export CSV ─────────────────────────────────────────────────────────────
injected_names = {s[0]: town for town, s, _ in injected} if injected else {}

with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['alert_rank','lat','lon','road','risk_score',
                                      'lanes_weight','nearby_alerts_marapr2026',
                                      'northern_sentinel'])
    w.writeheader()
    for rank, (lat, lon, risk, cw, rname, alerts) in enumerate(scored, 1):
        is_sentinel = any(
            abs(lat - s[0]) < 0.001 and abs(lon - s[1]) < 0.001
            for town, s, _ in injected
        ) if injected else False
        w.writerow({
            'alert_rank': rank,
            'lat': round(lat, 5),
            'lon': round(lon, 5),
            'road': rname,
            'risk_score': round(risk, 2),
            'lanes_weight': round(cw, 1),
            'nearby_alerts_marapr2026': alerts,
            'northern_sentinel': 'yes' if is_sentinel else '',
        })
print(f"Saved: {OUT_CSV.name}")

# ── 10. Tier summary ──────────────────────────────────────────────────────────
print("\n── Deployment tiers (Mar–Apr 2026) ──")
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
