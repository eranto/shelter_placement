"""
Fetch real OpenStreetMap tiles, stitch them, then overlay roads + shelter markers.
Saves road_shelters_map.jpg and road_shelters_budget.jpg.
"""
import math, io, time
import numpy as np
import requests
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

np.random.seed(7)
OUTPUT_MAP    = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_map.jpg"
OUTPUT_BUDGET = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_budget.jpg"

ZOOM = 9   # zoom 9: ~300 m/px — good detail for Israel

# ── OSM tile helpers ───────────────────────────────────────────────────────────
def lat_lon_to_tile(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

def tile_to_lon(x, z):
    return x / (2**z) * 360 - 180

def tile_to_lat(y, z):
    n = math.pi - 2*math.pi*y / (2**z)
    return math.degrees(math.atan(math.sinh(n)))

def fetch_tile(x, y, z, session, retries=3):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "road-shelter-mapper/1.0 (research)"}
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass
        time.sleep(0.5)
    return Image.new("RGB", (256, 256), (200, 200, 200))

# ── Bounding box (Israel + small margin) ──────────────────────────────────────
LAT_MAX, LAT_MIN = 33.45, 29.35
LON_MIN, LON_MAX = 34.15, 35.95

tx_min, ty_min = lat_lon_to_tile(LAT_MAX, LON_MIN, ZOOM)
tx_max, ty_max = lat_lon_to_tile(LAT_MIN, LON_MAX, ZOOM)

print(f"Tiles: x {tx_min}–{tx_max}  y {ty_min}–{ty_max}  "
      f"({tx_max-tx_min+1}×{ty_max-ty_min+1} = "
      f"{(tx_max-tx_min+1)*(ty_max-ty_min+1)} tiles)")

# ── Fetch & stitch ─────────────────────────────────────────────────────────────
n_cols = tx_max - tx_min + 1
n_rows = ty_max - ty_min + 1
mosaic = Image.new("RGB", (n_cols * 256, n_rows * 256))

session = requests.Session()
total_tiles = n_cols * n_rows
fetched = 0
for row, ty in enumerate(range(ty_min, ty_max + 1)):
    for col, tx in enumerate(range(tx_min, tx_max + 1)):
        tile = fetch_tile(tx, ty, ZOOM, session)
        mosaic.paste(tile, (col * 256, row * 256))
        fetched += 1
        if fetched % 5 == 0:
            print(f"  {fetched}/{total_tiles} tiles fetched…")
        time.sleep(0.05)   # be polite to OSM servers

print(f"Mosaic: {mosaic.size[0]}×{mosaic.size[1]} px")

# ── Coordinate converters (tile-space → pixel) ─────────────────────────────────
# Mosaic top-left corresponds to (tx_min, ty_min)
TILE_SIZE = 256
img_w, img_h = mosaic.size

def ll_to_px(lat, lon):
    """Convert lat/lon to pixel coordinates in the mosaic."""
    n = 2 ** ZOOM
    x_tile = (lon + 180) / 360 * n
    lat_r  = math.radians(lat)
    y_tile = (1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n
    px = (x_tile - tx_min) * TILE_SIZE
    py = (y_tile - ty_min) * TILE_SIZE
    return px, py

# ── Road network ──────────────────────────────────────────────────────────────
ROADS = [
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
    ("כביש 10 (גבול מצרים – רצועת עזה)",
     [(29.558,34.948),(30.050,34.580),(30.300,34.480),
      (30.700,34.450),(31.050,34.460),(31.220,34.420)], 4.0),
    ("כביש 99 (גליל עליון – גבול לבנון)",
     [(33.250,35.124),(33.224,35.217),(33.197,35.330),
      (33.172,35.440),(33.115,35.583),(33.081,35.693)], 4.0),
    ("כביש 978 / 899 (קו גבול לבנון)",
     [(33.272,35.101),(33.248,35.135),(33.220,35.185),
      (33.188,35.248),(33.155,35.310),(33.098,35.387),(33.072,35.420)], 4.0),
    ("כביש 89 (מעלות–ראש הנקרה)",
     [(32.980,35.045),(33.019,35.039),(33.050,35.025),(33.075,35.000)], 3.5),
    ("כביש 80 (עכו–מעלות–חרמון)",
     [(32.925,35.083),(33.010,35.143),(33.080,35.204)], 3.0),
    ("כביש 90 (עמק הירדן – צפון)",
     [(33.197,35.550),(32.970,35.490),(32.735,35.575),
      (32.500,35.535),(32.240,35.499)], 2.5),
    ("כביש 77 (עכו–נהריה)",
     [(32.925,35.083),(33.003,35.097),(33.017,35.100)], 2.0),
    ("כביש 98 (גולן – גבול סוריה)",
     [(32.750,35.780),(32.900,35.750),(33.050,35.700),
      (33.150,35.660),(33.250,35.620)], 3.0),
    ("כביש 91 (גולן רוחבי – קצרין)",
     [(32.985,35.490),(32.990,35.593),(32.990,35.690),(32.960,35.780)], 2.5),
    ("כביש 87 (טבריה–גולן)",
     [(32.793,35.531),(32.850,35.600),(32.960,35.680)], 2.0),
    ("כביש 90 (בקעת הירדן – ים המלח)",
     [(32.240,35.499),(32.000,35.488),(31.780,35.430),
      (31.550,35.436),(31.270,35.450),(30.980,35.434)], 2.5),
    ("כביש 90 (ערבה – אילת)",
     [(30.980,35.434),(30.600,35.250),(30.200,35.100),(29.558,34.948)], 2.0),
    ("כביש 40 (ניצנה–מצפה רמון–אילת)",
     [(30.870,34.430),(30.605,34.803),(30.380,34.880),
      (30.200,34.950),(29.870,35.022),(29.558,34.948)], 2.0),
    ("כביש 40 (באר שבע–אשקלון)",
     [(31.680,34.558),(31.556,34.600),(31.435,34.647),(31.270,34.797)], 2.5),
    ("כביש 6 (חוצה ישראל – מרכז–צפון)",
     [(32.080,34.930),(32.200,34.988),(32.350,35.003),
      (32.500,35.012),(32.650,35.058),(32.800,35.097),(32.870,35.100)], 1.5),
    ("כביש 6 (חוצה ישראל – דרום)",
     [(31.700,34.750),(31.850,34.798),(32.000,34.870),(32.080,34.930)], 1.5),
    ("כביש 1 (תל אביב–ירושלים)",
     [(32.082,34.781),(31.975,34.908),(31.905,34.987),
      (31.850,35.065),(31.793,35.172),(31.782,35.216)], 1.8),
    ("כביש 443 (מודיעין–ירושלים)",
     [(31.895,35.010),(31.855,35.075),(31.822,35.143),(31.800,35.210)], 1.8),
    ("כביש 2 (גוש דן–חדרה–חיפה)",
     [(32.082,34.781),(32.175,34.832),(32.320,34.870),
      (32.460,34.924),(32.620,34.961),(32.820,34.981),(32.920,35.012)], 1.4),
    ("כביש 4 (גוש דן–אשדוד–אשקלון)",
     [(32.082,34.781),(31.985,34.750),(31.870,34.715),
      (31.760,34.660),(31.680,34.583)], 2.0),
    ("כביש 3 (שפלה – לוד–ירושלים)",
     [(31.990,34.892),(31.900,34.900),(31.869,34.904),(31.820,35.050)], 1.3),
    ("כביש 38 (בית שמש–ירושלים)",
     [(31.780,35.214),(31.733,35.005),(31.697,34.990)], 1.3),
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
    ("כביש 60 (ירושלים–שכם, קטע ישראלי)",
     [(31.782,35.216),(31.870,35.220),(31.970,35.240),(32.120,35.260)], 1.8),
    ("כביש 31 (באר שבע–ערד–מצדה)",
     [(31.270,34.797),(31.267,35.000),(31.262,35.210),(31.190,35.344)], 1.8),
    ("כביש 25 / 204 (נגב דרום-מערב)",
     [(31.264,34.798),(31.100,34.650),(30.900,34.600),(30.700,34.550)], 2.5),
    ('כביש 5 (פ"ת–אריאל)',
     [(32.082,34.810),(32.082,34.950),(32.082,35.030),(32.100,35.105)], 1.5),
    ("כביש 57 (נתניה–טולכרם)",
     [(32.320,34.870),(32.310,34.990),(32.295,35.090)], 1.5),
    ("כביש 22 (נשר–חיפה–קרית אתא)",
     [(32.820,34.981),(32.830,35.020),(32.820,35.068),(32.806,35.096)], 1.3),
    ("כביש 96 (קרית שמונה–דן)",
     [(33.197,35.550),(33.230,35.564),(33.250,35.580)], 3.0),
]

def seg_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

def road_length_km(wpts):
    return sum(seg_km(wpts[i], wpts[i+1]) for i in range(len(wpts)-1))

def interpolate_km(wpts, spacing_km):
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total == 0:
        return [wpts[0]]
    distances = [0.0]
    d = spacing_km
    while d < total:
        distances.append(d)
        d += spacing_km
    distances.append(total)
    distances = sorted(set(distances))
    pts = []
    for target in distances:
        seg = np.searchsorted(cum, target, side='right') - 1
        seg = min(seg, len(wpts)-2)
        sl = cum[seg+1] - cum[seg]
        t = 0 if sl == 0 else (target - cum[seg]) / sl
        lat = wpts[seg][0] + t*(wpts[seg+1][0]-wpts[seg][0])
        lon = wpts[seg][1] + t*(wpts[seg+1][1]-wpts[seg][1])
        pts.append((lat, lon))
    return pts

def speed_kmh(risk):
    if risk >= 4.0: return 70
    if risk >= 3.0: return 80
    if risk >= 2.0: return 90
    return 110

def max_gap_km(risk):
    return 2 * (5/60) * speed_kmh(risk)

def risk_color(risk):
    if risk >= 4.0: return "#c0392b"
    if risk >= 3.0: return "#e67e22"
    if risk >= 2.0: return "#e6b800"
    return "#2ecc71"

shelter_points = []
road_stats = []
for name, wpts, risk in ROADS:
    km  = road_length_km(wpts)
    gap = max_gap_km(risk)
    pts = interpolate_km(wpts, gap)
    for lat, lon in pts:
        jlat = lat + np.random.uniform(-0.0015, 0.0015)
        jlon = lon + np.random.uniform(-0.002, 0.002)
        shelter_points.append((jlat, jlon, name, risk))
    road_stats.append((name, km, speed_kmh(risk), gap, len(pts), risk))

total = len(shelter_points)
print(f"\nShelters: {total}  |  Road network: {sum(r[1] for r in road_stats):.0f} km")

# ── Draw on mosaic ─────────────────────────────────────────────────────────────
# Work in pixel space using PIL for roads (lines), matplotlib for scatter + legend
fig, ax = plt.subplots(figsize=(14, 20), dpi=150)
ax.set_position([0, 0, 1, 1])
ax.axis('off')

# Show the tile mosaic
ax.imshow(np.array(mosaic), origin='upper', aspect='auto',
          extent=[0, img_w, img_h, 0])
ax.set_xlim(0, img_w)
ax.set_ylim(img_h, 0)

# Draw road polylines
for name, wpts, risk in ROADS:
    pxs = [ll_to_px(lat, lon) for lat, lon in wpts]
    xs = [p[0] for p in pxs]
    ys = [p[1] for p in pxs]
    lw = 2.8 if risk >= 3.5 else (2.2 if risk >= 2.5 else 1.8)
    # white outline for contrast
    ax.plot(xs, ys, color='white', linewidth=lw+2.0, alpha=0.6,
            solid_capstyle='round', solid_joinstyle='round', zorder=3)
    ax.plot(xs, ys, color=risk_color(risk), linewidth=lw, alpha=0.92,
            solid_capstyle='round', solid_joinstyle='round', zorder=4)

# Draw shelter markers
risk_groups = {}
for lat, lon, road, risk in shelter_points:
    risk_groups.setdefault(risk, []).append((lat, lon))

for risk in sorted(risk_groups.keys()):
    pts_ll = risk_groups[risk]
    pxs = [ll_to_px(lat, lon) for lat, lon in pts_ll]
    xs = [p[0] for p in pxs]
    ys = [p[1] for p in pxs]
    ms = 55 if risk >= 3.5 else (45 if risk >= 2.5 else 35)
    ax.scatter(xs, ys, s=ms, color=risk_color(risk),
               edgecolors='white', linewidths=0.8, zorder=6, alpha=0.95)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_elements = [
    mlines.Line2D([0],[0], color='#c0392b', lw=3,
                  label='Border / Gaza envelope road (70 km/h)'),
    mlines.Line2D([0],[0], color='#e67e22', lw=2.5,
                  label='High-risk road (80 km/h)'),
    mlines.Line2D([0],[0], color='#e6b800', lw=2,
                  label='Regional road (90 km/h)'),
    mlines.Line2D([0],[0], color='#2ecc71', lw=2,
                  label='Highway (110 km/h)'),
    mlines.Line2D([0],[0], marker='o', color='w',
                  markerfacecolor='#888', markersize=7,
                  label=f'Shelter (total: {total})'),
]
leg = ax.legend(handles=legend_elements,
                loc='lower left',
                fontsize=9,
                framealpha=0.90,
                edgecolor='#999',
                fancybox=True,
                title='5-minute standard  |  color = risk level',
                title_fontsize=9)

# ── Title box ─────────────────────────────────────────────────────────────────
ax.text(0.5, 0.985,
        f'Israeli Road Shelters  —  {total} units  |  5-minute standard  |  1,972 km network',
        transform=ax.transAxes,
        fontsize=13, fontweight='bold', ha='center', va='top',
        color='white',
        bbox=dict(boxstyle='round,pad=0.4', fc='#1a1a2e', ec='none', alpha=0.85),
        zorder=10)

plt.savefig(OUTPUT_MAP, dpi=150, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 93})
print(f"Map saved: {OUTPUT_MAP}")
plt.close()


# ══════════════════════════════════════════════════════════════════════════════
# Budget chart
# ══════════════════════════════════════════════════════════════════════════════
UNIT = {4.0: 520_000, 3.5: 520_000, 3.0: 460_000, 2.5: 430_000, 2.0: 430_000,
        1.8: 400_000, 1.5: 400_000, 1.4: 400_000, 1.3: 400_000}

def unit_cost(risk):
    if risk >= 4.0: return 520_000
    if risk >= 3.0: return 460_000
    if risk >= 2.0: return 430_000
    return 400_000

hi4 = [s for s in shelter_points if s[3] >= 4.0]
hi3 = [s for s in shelter_points if 3.0 <= s[3] < 4.0]
mid = [s for s in shelter_points if 2.0 <= s[3] < 3.0]
low = [s for s in shelter_points if s[3] < 2.0]

c4, c3, cm, cl = (len(hi4)*520_000, len(hi3)*460_000,
                  len(mid)*430_000, len(low)*400_000)
total_cap = c4 + c3 + cm + cl
contingency = total_cap * 0.15
total_with_cont = total_cap + contingency
maint_annual = total * 15_000

fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), facecolor='#F8F9FA')

# Left: by risk tier
cats   = ['Border roads\n(risk≥4)', 'High risk\n(risk 3–4)', 'Regional\n(risk 2–3)', 'Highways\n(risk<2)']
costs  = [c4/1e6, c3/1e6, cm/1e6, cl/1e6]
counts = [len(hi4), len(hi3), len(mid), len(low)]
colors = ['#c0392b','#e67e22','#e6b800','#2ecc71']

for a in (ax1, ax2):
    a.set_facecolor('#F8F9FA')
    a.yaxis.grid(True, linestyle='--', linewidth=0.6, color='#DDD')
    a.set_axisbelow(True)
    for sp in ['top','right']: a.spines[sp].set_visible(False)

bars1 = ax1.bar(cats, costs, color=colors, edgecolor='white', linewidth=1.5, width=0.55)
for bar, val, n in zip(bars1, costs, counts):
    ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.4,
             f'{val:.1f}M NIS\n({n} units)',
             ha='center', va='bottom', fontsize=10, fontweight='bold', color='#222')
ax1.set_ylabel('Million NIS', fontsize=11)
ax1.set_title('Capital cost by risk tier', fontsize=13, fontweight='bold', pad=12)
ax1.set_ylim(0, max(costs)*1.4)

# Right: summary
sl = ['Base\ncapex', '+15%\ncontingency', 'Annual\nmaint.', 'Total\n(capex+cont.)']
sv = [total_cap/1e6, contingency/1e6, maint_annual/1e6, total_with_cont/1e6]
sc = ['#2980b9','#e74c3c','#8e44ad','#1a5276']
bars2 = ax2.bar(sl, sv, color=sc, edgecolor='white', linewidth=1.5, width=0.55)
for bar, val in zip(bars2, sv):
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
             f'{val:.1f}M NIS', ha='center', va='bottom',
             fontsize=11, fontweight='bold', color='#222')
ax2.set_ylabel('Million NIS', fontsize=11)
ax2.set_title('Budget summary', fontsize=13, fontweight='bold', pad=12)
ax2.set_ylim(0, max(sv)*1.3)

fig2.suptitle(
    f'Budget estimate: {total} road shelters (מיגוניות)  —  5-minute standard  —  1,972 km network',
    fontsize=13, fontweight='bold', y=1.01)
fig2.text(0.5, -0.025,
          'Assumptions: 6-person prefab shelter unit | 400,000–520,000 NIS/unit capital | '
          '15,000 NIS/unit/year maintenance | prices excl. VAT | 15% contingency reserve',
          ha='center', fontsize=8.5, color='#555')

plt.tight_layout(pad=2.0)
plt.savefig(OUTPUT_BUDGET, dpi=150, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 93})
print(f"Budget chart saved: {OUTPUT_BUDGET}")
plt.close()

# Print summary
print("\n" + "="*56)
print(f"  Capital cost (base):          {total_cap/1e6:>6.1f}M NIS")
print(f"  Capital cost (+15% reserve):  {total_with_cont/1e6:>6.1f}M NIS")
print(f"  Annual maintenance:           {maint_annual/1e6:>6.2f}M NIS/yr")
print("="*56)
