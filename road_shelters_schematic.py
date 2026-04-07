"""
Clean schematic map of Israeli road shelters.
No basemap — just roads, shelters, city dots, labels on a minimal background.
"""
import math, numpy as np
from bidi.algorithm import get_display
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

def H(text):
    """Return visually-ordered Hebrew string for matplotlib."""
    return get_display(text)
from matplotlib.patches import FancyBboxPatch

np.random.seed(7)
OUT = ("/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/"
       "Kalay 2026 Trivago/Report/road_shelters_schematic.jpg")

# ── Road network ───────────────────────────────────────────────────────────────
ROADS = [
    ("232 (עוטף עזה)",
     [(31.416,34.291),(31.382,34.315),(31.354,34.336),
      (31.318,34.362),(31.275,34.398),(31.242,34.425)], 4.0),
    ("34 (נגב מערבי – עוטף)",
     [(31.680,34.558),(31.586,34.510),(31.490,34.476),
      (31.416,34.450),(31.360,34.430)], 3.5),
    ("35 (קרית גת – שדרות)",
     [(31.610,34.773),(31.551,34.703),(31.518,34.622),
      (31.476,34.547),(31.426,34.494)], 3.5),
    ("25 (נגב מרכזי)",
     [(31.264,34.798),(31.242,34.625),(31.220,34.430)], 3.0),
    ("99 (גליל עליון – גבול לבנון)",
     [(33.02,35.09),(33.05,35.19),(33.05,35.33),
      (33.08,35.44),(33.07,35.57),(33.07,35.69)], 4.0),
    ("978/899 (קו גבול לבנון)",
     [(33.05,35.09),(33.06,35.14),(33.08,35.18),
      (33.13,35.24),(33.14,35.31),(33.09,35.38),(33.07,35.42)], 4.0),
    ("89 (מעלות–ראש הנקרה)",
     [(32.980,35.045),(33.019,35.039),(33.050,35.025),(33.075,35.000)], 3.5),
    ("80 (עכו–מעלות)",
     [(32.925,35.083),(33.010,35.143),(33.080,35.204)], 3.0),
    ("90 (עמק הירדן – צפון)",
     [(33.197,35.550),(32.970,35.490),(32.735,35.575),
      (32.500,35.535),(32.240,35.499)], 2.5),
    ("77 (עכו–נהריה)",
     [(32.925,35.083),(33.003,35.097),(33.017,35.100)], 2.0),
    ("98 (גולן – גבול סוריה)",
     [(32.750,35.780),(32.900,35.750),(33.050,35.700),
      (33.150,35.660),(33.250,35.620)], 3.0),
    ("91 (גולן רוחבי)",
     [(32.985,35.490),(32.990,35.593),(32.990,35.690),(32.960,35.780)], 2.5),
    ("87 (טבריה–גולן)",
     [(32.793,35.531),(32.850,35.600),(32.960,35.680)], 2.0),
    ("90 (בקעת הירדן – ים המלח)",
     [(32.240,35.499),(32.000,35.488),(31.780,35.430),
      (31.550,35.436),(31.270,35.450),(30.980,35.434)], 2.5),
    ("90 (ערבה – אילת)",
     [(30.980,35.434),(30.600,35.250),(30.200,35.100),(29.558,34.948)], 2.0),
    ("40 (ניצנה–מצפה רמון–אילת)",
     [(30.870,34.430),(30.605,34.803),(30.380,34.880),
      (30.200,34.950),(29.870,35.022),(29.558,34.948)], 2.0),
    ("40 (באר שבע–אשקלון)",
     [(31.680,34.558),(31.556,34.600),(31.435,34.647),(31.270,34.797)], 2.5),
    ("6 (חוצה ישראל – צפון)",
     [(32.080,34.930),(32.200,34.988),(32.350,35.003),
      (32.500,35.012),(32.650,35.058),(32.800,35.097),(32.870,35.100)], 1.5),
    ("6 (חוצה ישראל – דרום)",
     [(31.700,34.750),(31.850,34.798),(32.000,34.870),(32.080,34.930)], 1.5),
    ("1 (תל אביב–ירושלים)",
     [(32.082,34.781),(31.975,34.908),(31.905,34.987),
      (31.850,35.065),(31.793,35.172),(31.782,35.216)], 1.8),
    ("443 (מודיעין–ירושלים)",
     [(31.895,35.010),(31.855,35.075),(31.822,35.143),(31.800,35.210)], 1.8),
    ("2 (חוף – גוש דן–חיפה)",
     [(32.082,34.781),(32.175,34.832),(32.320,34.870),
      (32.460,34.924),(32.620,34.961),(32.820,34.981),(32.920,35.012)], 1.4),
    ("4 (גוש דן–אשדוד–אשקלון)",
     [(32.082,34.781),(31.985,34.750),(31.870,34.715),
      (31.760,34.660),(31.680,34.583)], 2.0),
    ("3 (שפלה)",
     [(31.990,34.892),(31.900,34.900),(31.869,34.904),(31.820,35.050)], 1.3),
    ("38 (בית שמש–ירושלים)",
     [(31.780,35.214),(31.733,35.005),(31.697,34.990)], 1.3),
    ("85 (עכו–טבריה)",
     [(32.925,35.083),(32.874,35.156),(32.845,35.258),
      (32.808,35.388),(32.770,35.491)], 2.0),
    ("65 (וואדי ערה)",
     [(32.562,35.185),(32.517,35.104),(32.487,35.001),(32.461,34.942)], 1.8),
    ("70 (חיפה–זכרון–חדרה)",
     [(32.820,34.981),(32.720,34.960),(32.620,34.944),(32.500,34.918)], 1.4),
    ("75/79 (נצרת–עפולה)",
     [(32.700,35.303),(32.650,35.225),(32.606,35.188),
      (32.590,35.109),(32.562,35.050)], 1.4),
    ("60 (ירושלים–שכם)",
     [(31.782,35.216),(31.870,35.220),(31.970,35.240),(32.120,35.260)], 1.8),
    ("31 (באר שבע–ערד)",
     [(31.270,34.797),(31.267,35.000),(31.262,35.210),(31.190,35.344)], 1.8),
    ("25/204 (נגב דרום)",
     [(31.264,34.798),(31.100,34.650),(30.900,34.600),(30.700,34.550)], 2.5),
    ("5 (פ\"ת–אריאל)",
     [(32.082,34.810),(32.082,34.950),(32.082,35.030),(32.100,35.105)], 1.5),
    ("57 (נתניה–טולכרם)",
     [(32.320,34.870),(32.310,34.990),(32.295,35.090)], 1.5),
    ("22 (חיפה–קרית אתא)",
     [(32.820,34.981),(32.830,35.020),(32.820,35.068),(32.806,35.096)], 1.3),
    ("96 (קרית שמונה–דן)",
     [(33.197,35.550),(33.230,35.564),(33.250,35.580)], 3.0),
]

# ── Geometry helpers ───────────────────────────────────────────────────────────
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

# Risk colours
C = {4.0: '#D63031', 3.5: '#D63031', 3.0: '#E17055',
     2.5: '#FDCB6E', 2.0: '#FDCB6E', 1.8: '#00B894',
     1.5: '#00B894', 1.4: '#00B894', 1.3: '#00B894'}

def rc(risk):
    if risk >= 3.5: return '#D63031'
    if risk >= 2.5: return '#E17055'
    if risk >= 1.8: return '#FDCB6E'
    return '#00B894'

# Place shelters
shelter_points = []
for name, wpts, risk in ROADS:
    for lat, lon in interpolate_km(wpts, max_gap(risk)):
        jlat = lat + np.random.uniform(-0.0005, 0.0005)
        jlon = lon + np.random.uniform(-0.0007, 0.0007)
        shelter_points.append((jlat, jlon, risk))

total = len(shelter_points)

# ── Figure ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 19))
fig.patch.set_facecolor('#1E272E')
ax.set_facecolor('#1E272E')

# Subtle grid
for lat in np.arange(29.5, 33.5, 0.5):
    ax.axhline(lat, color='#2D3436', linewidth=0.4, zorder=1)
for lon in np.arange(34.2, 36.0, 0.5):
    ax.axvline(lon, color='#2D3436', linewidth=0.4, zorder=1)

# Mediterranean Sea label
ax.text(34.38, 31.85, H('ים תיכון'), fontsize=11, color='#4A6FA5',
        ha='center', va='center', style='italic',
        fontfamily='Arial Hebrew', alpha=0.7, zorder=2)

# Dead Sea
ax.text(35.50, 31.42, H('ים המלח'), fontsize=8, color='#4A6FA5',
        ha='center', va='center', style='italic',
        fontfamily='Arial Hebrew', alpha=0.6, zorder=2)

# Draw roads — thick white halo then colored line
for name, wpts, risk in ROADS:
    lons = [p[1] for p in wpts]
    lats = [p[0] for p in wpts]
    lw = 3.2 if risk >= 3.5 else (2.6 if risk >= 2.5 else 2.0)
    ax.plot(lons, lats, color='white', lw=lw+2.5, alpha=0.12,
            solid_capstyle='round', solid_joinstyle='round', zorder=3)
    ax.plot(lons, lats, color=rc(risk), lw=lw, alpha=0.95,
            solid_capstyle='round', solid_joinstyle='round', zorder=4)

# Draw shelters (group by risk for single legend handles)
for tier, col, ms in [
    (lambda r: r >= 3.5, '#D63031', 52),
    (lambda r: 2.5 <= r < 3.5, '#E17055', 42),
    (lambda r: 1.8 <= r < 2.5, '#FDCB6E', 32),
    (lambda r: r < 1.8, '#00B894', 26),
]:
    pts = [(lon, lat) for lat, lon, risk in shelter_points if tier(risk)]
    if pts:
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=ms, color=col, edgecolors='#1E272E',
                   linewidths=0.7, zorder=6, alpha=0.97)

# ── City markers ───────────────────────────────────────────────────────────────
# (lat, lon, label, offset_lon, offset_lat, size)
CITIES = [
    (32.082, 34.781, "תל אביב",    -0.05, -0.06, 10, True),
    (31.782, 35.216, "ירושלים",     0.05, -0.06, 10, True),
    (32.820, 34.981, "חיפה",        0.05,  0.05,  9, True),
    (31.252, 34.791, "באר שבע",    -0.05, -0.07,  9, True),
    (29.558, 34.948, "אילת",       -0.05, -0.07,  8, False),
    (33.207, 35.569, "קרית שמונה",  0.05,  0.05,  7.5, False),
    (32.793, 35.531, "טבריה",       0.05,  0.04,  7.5, False),
    (32.330, 34.860, "נתניה",      -0.05,  0.04,  7.5, False),
    (31.800, 34.650, "אשדוד",      -0.06,  0.04,  7.5, False),
    (31.674, 34.571, "אשקלון",     -0.06, -0.06,  7.5, False),
    (31.526, 34.596, "שדרות",      -0.06,  0.04,  7,   False),
    (32.925, 35.083, "עכו",         0.05,  0.04,  7.5, False),
    (32.990, 35.690, "קצרין",       0.05,  0.04,  7.5, False),
    (30.605, 34.803, "מצפה רמון",  -0.05,  0.05,  7,   False),
    (32.700, 35.303, "נצרת",        0.05,  0.04,  7.5, False),
    (33.080, 35.200, "מעלות",       0.05,  0.04,  7,   False),
]

for lat, lon, label, dlon, dlat, fs, bold in CITIES:
    # City dot (white)
    ax.scatter([lon], [lat], s=55, color='white', edgecolors='#636E72',
               linewidths=1.2, zorder=8)
    ax.text(lon + dlon, lat + dlat, H(label),
            fontsize=fs,
            fontweight='bold' if bold else 'normal',
            color='#DFE6E9',
            fontfamily='Arial Hebrew',
            ha='center', va='center',
            zorder=9)

# ── Border labels ──────────────────────────────────────────────────────────────
ax.text(35.75, 33.30, H('לבנון'), fontsize=7.5, color='#B2BEC3',
        ha='right', fontfamily='Arial Hebrew', style='italic', zorder=9)
ax.text(35.85, 33.15, H('סוריה'), fontsize=7.5, color='#B2BEC3',
        ha='right', fontfamily='Arial Hebrew', style='italic', zorder=9)
ax.text(34.35, 29.50, H('מצרים'), fontsize=7.5, color='#B2BEC3',
        ha='left', fontfamily='Arial Hebrew', style='italic', zorder=9)
ax.text(35.90, 31.50, H('ירדן'), fontsize=7.5, color='#B2BEC3',
        ha='right', fontfamily='Arial Hebrew', style='italic', zorder=9)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mlines.Line2D([],[],color='#D63031',lw=3,   label=H('כביש גבול / עוטף עזה  |  70 קמ"ש')),
    mlines.Line2D([],[],color='#E17055',lw=2.6, label=H('כביש סיכון גבוה  |  80 קמ"ש')),
    mlines.Line2D([],[],color='#FDCB6E',lw=2.2, label=H('כביש אזורי  |  90 קמ"ש')),
    mlines.Line2D([],[],color='#00B894',lw=2,   label=H('כביש מהיר  |  110 קמ"ש')),
    mlines.Line2D([],[],marker='o',color='none',markerfacecolor='#DFE6E9',
                  markersize=7, label=H(f'מיגונית  (סה"כ: {total})')),
]
leg = ax.legend(handles=legend_items,
                loc='lower left',
                fontsize=8.5,
                framealpha=0.85,
                facecolor='#2D3436',
                edgecolor='#636E72',
                labelcolor='#DFE6E9',
                title=H('תקן אחיד: 5 דקות'),
                title_fontsize=9,
                prop={'family': 'Arial Hebrew', 'size': 8.5})
leg.get_title().set_color('#DFE6E9')
leg.get_title().set_fontfamily('Arial Hebrew')

# ── Title ─────────────────────────────────────────────────────────────────────
ax.set_title(H(f'מיגוניות בכבישי ישראל — {total} יחידות  |  תקן: הגעה תוך 5 דקות'),
             fontsize=14, fontweight='bold', color='#DFE6E9',
             fontfamily='Arial Hebrew', pad=14)

# Stats box — each line separately so bidi works per-line
for i, line in enumerate([
    H(f'רשת כבישים: 1,972 ק"מ'),
    H(f'מיגוניות: {total} יחידות'),
    H('עלות הון: ~94M NIS'),
    H('תחזוקה: ~2.8M NIS/שנה'),
]):
    ax.text(35.87, 29.55 + i*0.13, line,
            fontsize=8, color='#B2BEC3',
            fontfamily='Arial Hebrew',
            ha='right', va='bottom',
            zorder=10)
ax.add_patch(mpatches.FancyBboxPatch(
    (35.10, 29.52), 0.77, 0.60,
    boxstyle='round,pad=0.04', fc='#2D3436', ec='#636E72', alpha=0.85, zorder=9))

# Axes
ax.set_xlim(34.18, 35.92)
ax.set_ylim(29.35, 33.45)
ax.set_xlabel(H('קו אורך'), fontsize=8, color='#636E72')
ax.set_ylabel(H('קו רוחב'), fontsize=8, color='#636E72')
ax.tick_params(colors='#636E72', labelsize=7)
for spine in ax.spines.values():
    spine.set_edgecolor('#636E72')

plt.tight_layout(pad=1.2)
plt.savefig(OUT, dpi=200, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 94})
print(f"Saved: {OUT}")
plt.close()
