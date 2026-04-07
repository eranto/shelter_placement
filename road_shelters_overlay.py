"""
Overlay shelter markers on the existing 'Israeli Roads.jpg' background map.
"""
import math, numpy as np
from bidi.algorithm import get_display
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

np.random.seed(7)
IMG_PATH = ("/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/"
            "Kalay 2026 Trivago/Report/Israeli Roads.jpg")
OUT = ("/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/"
       "Kalay 2026 Trivago/Report/road_shelters_overlay.jpg")

def H(t): return get_display(t)

# ── Load background image ──────────────────────────────────────────────────────
bg = Image.open(IMG_PATH).convert('RGB')
W, H_px = bg.size          # 200 × 523
print(f"Background: {W}×{H_px} px")

# ── Geographic calibration ─────────────────────────────────────────────────────
# Calibrated by matching labeled cities to pixel positions.
# Adjust these 4 values if markers look off.
LON_MIN, LON_MAX = 34.00, 36.00   # left → right edge of image
LAT_MAX, LAT_MIN = 33.35, 29.45   # top  → bottom of map area
# The bottom ~33 px are a gray legend strip — map area ends at y≈490
MAP_TOP_PX  = 8      # first row of actual map content
MAP_BOT_PX  = 490    # last row of actual map content
MAP_LEFT_PX = 0
MAP_RIGHT_PX = W

def ll_to_px(lat, lon):
    """Convert lat/lon to (x, y) pixel in the image."""
    frac_x = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    frac_y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN)
    x = MAP_LEFT_PX  + frac_x * (MAP_RIGHT_PX - MAP_LEFT_PX)
    y = MAP_TOP_PX   + frac_y * (MAP_BOT_PX   - MAP_TOP_PX)
    return x, y

# ── Road network ───────────────────────────────────────────────────────────────
ROADS = [
    ("232", [(31.416,34.291),(31.382,34.315),(31.354,34.336),
             (31.318,34.362),(31.275,34.398),(31.242,34.425)], 4.0),
    ("34",  [(31.680,34.558),(31.586,34.510),(31.490,34.476),
             (31.416,34.450),(31.360,34.430)], 3.5),
    ("35",  [(31.610,34.773),(31.551,34.703),(31.518,34.622),
             (31.476,34.547),(31.426,34.494)], 3.5),
    ("25",  [(31.264,34.798),(31.242,34.625),(31.220,34.430)], 3.0),
    ("99",  [(33.02,35.09),(33.05,35.19),(33.05,35.33),
             (33.08,35.44),(33.07,35.57),(33.07,35.69)], 4.0),
    ("978", [(33.05,35.09),(33.06,35.14),(33.08,35.18),
             (33.13,35.24),(33.14,35.31),(33.09,35.38),(33.07,35.42)], 4.0),
    ("89",  [(32.980,35.045),(33.019,35.039),(33.050,35.025),(33.075,35.000)], 3.5),
    ("80",  [(32.925,35.083),(33.010,35.143),(33.080,35.204)], 3.0),
    ("90N", [(33.197,35.550),(32.970,35.490),(32.735,35.575),
             (32.500,35.535),(32.240,35.499)], 2.5),
    ("77",  [(32.925,35.083),(33.003,35.097),(33.017,35.100)], 2.0),
    ("98",  [(32.750,35.780),(32.900,35.750),(33.050,35.700),
             (33.150,35.660),(33.250,35.620)], 3.0),
    ("91",  [(32.985,35.490),(32.990,35.593),(32.990,35.690),(32.960,35.780)], 2.5),
    ("87",  [(32.793,35.531),(32.850,35.600),(32.960,35.680)], 2.0),
    ("90M", [(32.240,35.499),(32.000,35.488),(31.780,35.430),
             (31.550,35.436),(31.270,35.450),(30.980,35.434)], 2.5),
    ("90S", [(30.980,35.434),(30.600,35.250),(30.200,35.100),(29.558,34.948)], 2.0),
    ("40S", [(30.870,34.430),(30.605,34.803),(30.380,34.880),
             (30.200,34.950),(29.870,35.022),(29.558,34.948)], 2.0),
    ("40N", [(31.680,34.558),(31.556,34.600),(31.435,34.647),(31.270,34.797)], 2.5),
    ("6N",  [(32.080,34.930),(32.200,34.988),(32.350,35.003),
             (32.500,35.012),(32.650,35.058),(32.800,35.097),(32.870,35.100)], 1.5),
    ("6S",  [(31.700,34.750),(31.850,34.798),(32.000,34.870),(32.080,34.930)], 1.5),
    ("1",   [(32.082,34.781),(31.975,34.908),(31.905,34.987),
             (31.850,35.065),(31.793,35.172),(31.782,35.216)], 1.8),
    ("443", [(31.895,35.010),(31.855,35.075),(31.822,35.143),(31.800,35.210)], 1.8),
    ("2",   [(32.082,34.781),(32.175,34.832),(32.320,34.870),
             (32.460,34.924),(32.620,34.961),(32.820,34.981),(32.920,35.012)], 1.4),
    ("4",   [(32.082,34.781),(31.985,34.750),(31.870,34.715),
             (31.760,34.660),(31.680,34.583)], 2.0),
    ("3",   [(31.990,34.892),(31.900,34.900),(31.869,34.904),(31.820,35.050)], 1.3),
    ("38",  [(31.780,35.214),(31.733,35.005),(31.697,34.990)], 1.3),
    ("85",  [(32.925,35.083),(32.874,35.156),(32.845,35.258),
             (32.808,35.388),(32.770,35.491)], 2.0),
    ("65",  [(32.562,35.185),(32.517,35.104),(32.487,35.001),(32.461,34.942)], 1.8),
    ("70",  [(32.820,34.981),(32.720,34.960),(32.620,34.944),(32.500,34.918)], 1.4),
    ("75",  [(32.700,35.303),(32.650,35.225),(32.606,35.188),
             (32.590,35.109),(32.562,35.050)], 1.4),
    ("60",  [(31.782,35.216),(31.870,35.220),(31.970,35.240),(32.120,35.260)], 1.8),
    ("31",  [(31.270,34.797),(31.267,35.000),(31.262,35.210),(31.190,35.344)], 1.8),
    ("25S", [(31.264,34.798),(31.100,34.650),(30.900,34.600),(30.700,34.550)], 2.5),
    ("5",   [(32.082,34.810),(32.082,34.950),(32.082,35.030),(32.100,35.105)], 1.5),
    ("57",  [(32.320,34.870),(32.310,34.990),(32.295,35.090)], 1.5),
    ("22",  [(32.820,34.981),(32.830,35.020),(32.820,35.068),(32.806,35.096)], 1.3),
    ("96",  [(33.197,35.550),(33.230,35.564),(33.250,35.580)], 3.0),
]

def seg_km(p1, p2):
    dlat = (p2[0]-p1[0]) * 111.0
    dlon = (p2[1]-p1[1]) * 111.0 * math.cos(math.radians((p1[0]+p2[0])/2))
    return math.sqrt(dlat**2 + dlon**2)

def interpolate_km(wpts, spacing_km):
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total == 0: return [wpts[0]]
    dists = [0.0]
    d = spacing_km
    while d < total:
        dists.append(d); d += spacing_km
    dists.append(total)
    pts = []
    for tgt in sorted(set(dists)):
        seg = min(np.searchsorted(cum, tgt, side='right')-1, len(wpts)-2)
        sl = cum[seg+1]-cum[seg]
        t = 0 if sl == 0 else (tgt-cum[seg])/sl
        pts.append((wpts[seg][0]+t*(wpts[seg+1][0]-wpts[seg][0]),
                    wpts[seg][1]+t*(wpts[seg+1][1]-wpts[seg][1])))
    return pts

def speed_kmh(risk):
    if risk >= 4.0: return 70
    if risk >= 3.0: return 80
    if risk >= 2.0: return 90
    return 110

def max_gap(risk): return 2*(5/60)*speed_kmh(risk)

def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#F9CA24'
    return '#6AB04C'

# Place shelters
shelter_points = []
for name, wpts, risk in ROADS:
    for lat, lon in interpolate_km(wpts, max_gap(risk)):
        jlat = lat + np.random.uniform(-0.0005, 0.0005)
        jlon = lon + np.random.uniform(-0.0007, 0.0007)
        shelter_points.append((jlat, jlon, risk))

total = len(shelter_points)
print(f"Shelters: {total}")

# ── Figure: image fills the axes exactly ──────────────────────────────────────
# Scale up for print quality — multiply pixel coords by SCALE
DPI = 300
fig_w = W / DPI * 6    # 6x upscale
fig_h = H_px / DPI * 6

fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax.axis('off')

# Show background
ax.imshow(np.array(bg), extent=[0, W, H_px, 0], aspect='auto', zorder=1)
ax.set_xlim(0, W)
ax.set_ylim(H_px, 0)

# ── Draw shelter markers ───────────────────────────────────────────────────────
for tier, col, ms, ew in [
    (lambda r: r >= 3.5, '#D63031', 80, 0.8),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 65, 0.7),
    (lambda r: 1.8 <= r < 2.5, '#F9CA24', 50, 0.6),
    (lambda r: r < 1.8, '#6AB04C', 40, 0.5),
]:
    pts = [ll_to_px(lat, lon) for lat, lon, risk in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col,
                   edgecolors='white', linewidths=ew,
                   zorder=5, alpha=0.92)

# ── Legend panel drawn over the bottom gray strip ─────────────────────────────
legend_items = [
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#D63031',
                  markersize=5, label=H('כביש גבול / עוטף עזה  (70 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#E17055',
                  markersize=5, label=H('כביש סיכון גבוה  (80 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#F9CA24',
                  markersize=5, label=H('כביש אזורי  (90 קמ"ש)')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#6AB04C',
                  markersize=5, label=H('כביש מהיר  (110 קמ"ש)')),
]
leg = ax.legend(handles=legend_items,
                loc='lower right',
                fontsize=5.5,
                framealpha=0.88,
                facecolor='white',
                edgecolor='#aaa',
                labelcolor='#111',
                title=H(f'מיגוניות: {total} יח׳  |  תקן 5 דקות'),
                title_fontsize=6,
                prop={'size': 5.5},
                borderpad=0.6,
                labelspacing=0.4)
leg.get_title().set_color('#1a1a2e')

plt.savefig(OUT, dpi=DPI, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 95})
print(f"Saved: {OUT}")
plt.close()
