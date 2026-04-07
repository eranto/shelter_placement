"""
Generate a detailed JPEG map of Israeli road shelters (מיגוניות)
and print the budget estimate.
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
from matplotlib.patches import FancyArrowPatch

np.random.seed(7)
OUTPUT_MAP    = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_map.jpg"
OUTPUT_BUDGET = "/Users/erantoch/My Drive (erantoch@gmail.com)/Consulting/Kalay 2026 Trivago/Report/road_shelters_budget.jpg"

# ── Road network (same as road_shelters_7min.py) ───────────────────────────────
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
    ("כביש 60 (ירושלים–רמאללה–שכם, קטע ישראלי)",
     [(31.782,35.216),(31.870,35.220),(31.970,35.240),(32.120,35.260)], 1.8),
    ("כביש 31 (באר שבע–ערד–מצדה)",
     [(31.270,34.797),(31.267,35.000),(31.262,35.210),(31.190,35.344)], 1.8),
    ("כביש 25 / 204 (נגב דרום-מערב)",
     [(31.264,34.798),(31.100,34.650),(30.900,34.600),(30.700,34.550)], 2.5),
    ("כביש 5 (אריאל–פ\"ת–גוש דן)",
     [(32.082,34.810),(32.082,34.950),(32.082,35.030),(32.100,35.105)], 1.5),
    ("כביש 57 (נתניה–טולכרם–בקעה)",
     [(32.320,34.870),(32.310,34.990),(32.295,35.090)], 1.5),
    ("כביש 22 (נשר–חיפה–קרית אתא)",
     [(32.820,34.981),(32.830,35.020),(32.820,35.068),(32.806,35.096)], 1.3),
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
    cum = [0.0]
    for i in range(len(wpts)-1):
        cum.append(cum[-1] + seg_km(wpts[i], wpts[i+1]))
    total = cum[-1]
    if total == 0:
        return [wpts[0], wpts[-1]]
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

def max_gap_km(risk):
    return 2 * (5/60) * speed_kmh(risk)   # 5-min standard everywhere

# ── Place shelters ─────────────────────────────────────────────────────────────
shelter_points = []
road_stats = []
for name, wpts, risk in ROADS:
    km      = road_length_km(wpts)
    gap     = max_gap_km(risk)
    pts     = interpolate_km(wpts, gap)
    for lat, lon in pts:
        jlat = lat + np.random.uniform(-0.0015, 0.0015)
        jlon = lon + np.random.uniform(-0.002,  0.002)
        shelter_points.append((jlat, jlon, name, risk))
    road_stats.append((name, km, speed_kmh(risk), gap, len(pts), risk))

total = len(shelter_points)

# ── Color map ──────────────────────────────────────────────────────────────────
def risk_color(risk):
    if risk >= 4.0: return "#c0392b"
    if risk >= 3.0: return "#e67e22"
    if risk >= 2.0: return "#e6b800"
    return "#27ae60"

def road_lw(risk):
    if risk >= 3.5: return 2.5
    if risk >= 2.5: return 2.0
    return 1.5

# ── Israel approximate land outline ───────────────────────────────────────────
# Approximate polygon: Mediterranean coast + Negev + Jordan rift + Lebanon border
COAST = [
    (33.09, 35.10),  # Rosh HaNikra
    (33.01, 35.10),  # Nahariya
    (32.82, 34.98),  # Haifa
    (32.62, 34.96),  # Zichron
    (32.33, 34.86),  # Netanya
    (32.08, 34.78),  # Tel Aviv
    (31.99, 34.75),  # Rishon
    (31.80, 34.65),  # Ashdod
    (31.67, 34.57),  # Ashkelon
    (31.54, 34.55),  # Gaza area
    (31.23, 34.47),  # Rafah
    (30.87, 34.46),  # Nitzana
    (30.50, 34.54),  # Negev
    (29.56, 34.95),  # Eilat
    (29.56, 35.00),  # Aqaba
    (30.00, 35.18),  # Arava
    (30.60, 35.28),
    (31.00, 35.45),
    (31.27, 35.57),  # Dead Sea south
    (31.55, 35.57),  # Dead Sea north
    (31.78, 35.57),
    (32.24, 35.56),  # Jordan valley
    (32.74, 35.78),  # Golan south
    (33.25, 35.78),  # Golan north / Hermon
    (33.25, 35.58),  # Metula
    (33.25, 35.13),  # Lebanon border west
    (33.09, 35.10),  # back to Rosh HaNikra
]

# ── Figure 1: main map ─────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 22), facecolor='#EEF2F7')
ax.set_facecolor('#D6E8F5')  # sea blue

# Draw land
coast_lats = [p[0] for p in COAST]
coast_lons = [p[1] for p in COAST]
ax.fill(coast_lons, coast_lats, color='#F5F0E8', zorder=1, linewidth=0)
ax.plot(coast_lons, coast_lats, color='#8B7355', linewidth=0.8, zorder=2)

# Draw Negev / desert shading (approximate triangle)
negev_lat = [31.27, 30.87, 29.56, 30.50, 31.27]
negev_lon = [34.80, 34.46, 34.95, 34.54, 34.80]
ax.fill(negev_lon, negev_lat, color='#EDE0C4', zorder=2, alpha=0.5, linewidth=0)

# Draw roads
for name, wpts, risk in ROADS:
    lats = [p[0] for p in wpts]
    lons = [p[1] for p in wpts]
    ax.plot(lons, lats,
            color=risk_color(risk),
            linewidth=road_lw(risk),
            solid_capstyle='round',
            solid_joinstyle='round',
            zorder=4,
            alpha=0.85)

# Draw shelter points (grouped by risk for zorder)
risk_groups = {}
for lat, lon, road, risk in shelter_points:
    risk_groups.setdefault(risk, []).append((lat, lon))

for risk in sorted(risk_groups.keys()):
    pts = risk_groups[risk]
    lats_s = [p[0] for p in pts]
    lons_s = [p[1] for p in pts]
    ms = 7 if risk >= 3.5 else (6 if risk >= 2.5 else 5)
    ax.scatter(lons_s, lats_s,
               s=ms**2,
               color=risk_color(risk),
               edgecolors='white',
               linewidths=0.6,
               zorder=6,
               alpha=0.92)

# ── City labels ────────────────────────────────────────────────────────────────
# (lat, lon, label, ha, fontsize, bold, italic)
CITIES = [
    (32.082, 34.781, "תל אביב",    'right', 8.5, True,  False),
    (31.782, 35.216, "ירושלים",    'left',  8.5, True,  False),
    (32.820, 34.981, "חיפה",       'left',  8,   False, False),
    (31.252, 34.791, "באר שבע",    'right', 8,   False, False),
    (29.558, 34.948, "אילת",       'right', 8,   False, False),
    (33.207, 35.569, "קרית שמונה", 'left',  7.5, False, False),
    (32.793, 35.531, "טבריה",      'left',  7.5, False, False),
    (32.330, 34.860, "נתניה",      'right', 7.5, False, False),
    (31.800, 34.650, "אשדוד",      'right', 7.5, False, False),
    (31.674, 34.571, "אשקלון",     'right', 7.5, False, False),
    (31.526, 34.596, "שדרות",      'right', 7,   False, False),
    (32.925, 35.083, "עכו",        'left',  7.5, False, False),
    (32.990, 35.690, "קצרין",      'left',  7.5, False, False),
    (30.605, 34.803, "מצפה רמון",  'right', 7,   False, False),
    (31.270, 35.200, "ים המלח",    'center',7,   False, True),
]

for lat, lon, name, ha, fs, bold, italic in CITIES:
    ax.text(lon, lat, name,
            fontsize=fs,
            fontweight='bold' if bold else 'normal',
            fontstyle='italic' if italic else 'normal',
            ha=ha, va='center',
            color='#1a1a2e',
            fontfamily='Arial Hebrew',
            zorder=8,
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.65))

# ── Legend ─────────────────────────────────────────────────────────────────────
legend_elements = [
    mlines.Line2D([0],[0], color='#c0392b', lw=2.5,
                  label='כביש גבול / עוטף עזה (70 קמ"ש)'),
    mlines.Line2D([0],[0], color='#e67e22', lw=2.0,
                  label='כביש סיכון גבוה (80 קמ"ש)'),
    mlines.Line2D([0],[0], color='#e6b800', lw=1.8,
                  label='כביש אזורי (90 קמ"ש)'),
    mlines.Line2D([0],[0], color='#27ae60', lw=1.5,
                  label='כביש מהיר (110 קמ"ש)'),
    mlines.Line2D([0],[0], marker='o', color='w',
                  markerfacecolor='#555', markersize=6,
                  label=f'מיגונית (סה"כ {total})'),
]
leg = ax.legend(handles=legend_elements,
                loc='lower left',
                fontsize=9,
                framealpha=0.92,
                edgecolor='#aaa',
                title='תקן אחיד: 5 דקות לכל כביש',
                title_fontsize=9.5,
                prop={'family': 'Arial Hebrew', 'size': 9})
leg.get_title().set_fontfamily('Arial Hebrew')

# ── Title ──────────────────────────────────────────────────────────────────────
ax.set_title(f'מיגוניות בכבישי ישראל — {total} יחידות | תקן: הגעה תוך 5 דקות\n'
             f'1,972 ק"מ כבישים בין-עירוניים | צבע לפי רמת סיכון/מהירות',
             fontsize=14, fontweight='bold',
             fontfamily='Arial Hebrew',
             pad=14, color='#1A1A2E')

# Axes cosmetics
ax.set_xlim(34.20, 35.90)
ax.set_ylim(29.40, 33.40)
ax.set_xlabel('קו אורך', fontsize=9, color='#555')
ax.set_ylabel('קו רוחב', fontsize=9, color='#555')
ax.tick_params(labelsize=8)
ax.grid(True, linestyle=':', linewidth=0.4, color='#aaa', alpha=0.6, zorder=0)

# North arrow
ax.annotate('N', xy=(35.77, 33.25), xytext=(35.77, 33.10),
            fontsize=13, fontweight='bold', ha='center', color='#333',
            fontfamily='Arial',
            arrowprops=dict(arrowstyle='->', color='#333', lw=1.5),
            zorder=10)

# Scale bar (~50 km at lat 31.5)
scale_lon0, scale_lon1 = 34.30, 34.79   # ~50 km at lat ~31
scale_lat = 29.60
ax.plot([scale_lon0, scale_lon1], [scale_lat, scale_lat],
        color='#333', linewidth=2.5, zorder=10)
ax.plot([scale_lon0, scale_lon0], [scale_lat-0.04, scale_lat+0.04], color='#333', lw=2, zorder=10)
ax.plot([scale_lon1, scale_lon1], [scale_lat-0.04, scale_lat+0.04], color='#333', lw=2, zorder=10)
ax.text((scale_lon0+scale_lon1)/2, scale_lat-0.12, '50 ק"מ',
        ha='center', fontsize=8, color='#333', fontfamily='Arial Hebrew', zorder=10)

plt.tight_layout(pad=1.5)
plt.savefig(OUTPUT_MAP, dpi=200, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 92, 'optimize': True})
print(f"Map saved: {OUTPUT_MAP}")
plt.close()


# ══════════════════════════════════════════════════════════════════════════════
# ── Budget calculation ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# Shelter cost assumptions (NIS):
#   מיגונית standard 6-person prefab unit  ~220,000 ₪  (market range 150k–300k)
#   Foundation + civil works               ~ 80,000 ₪
#   Electrical / lighting / signage        ~ 25,000 ₪
#   Access path / paving (avg)             ~ 30,000 ₪
#   Engineering & permits (per unit)       ~ 15,000 ₪
#   Logistics & installation               ~ 30,000 ₪
#   ─────────────────────────────────────────────────
#   Unit total (base)                      ~400,000 ₪
#
#   High-risk zone uplift (+30%):          ~520,000 ₪
#   Remote / Negev uplift (+15%):          ~460,000 ₪
#
# Annual maintenance: ~15,000 ₪/unit/year

UNIT_BASE      = 400_000   # NIS per shelter, standard roads
UNIT_HIGH_RISK = 520_000   # NIS, risk >= 4.0 (border area, extra protection)
UNIT_ELEVATED  = 460_000   # NIS, risk 3.0–3.9 (elevated, some remote)
UNIT_REMOTE    = 430_000   # NIS, risk 2.0–2.9 (some desert/Jordan valley)
MAINTENANCE    = 15_000    # NIS/unit/year

hi4  = [(lat,lon,r) for lat,lon,_,r in shelter_points if r >= 4.0]
hi3  = [(lat,lon,r) for lat,lon,_,r in shelter_points if 3.0 <= r < 4.0]
mid  = [(lat,lon,r) for lat,lon,_,r in shelter_points if 2.0 <= r < 3.0]
low  = [(lat,lon,r) for lat,lon,_,r in shelter_points if r < 2.0]

cost_hi4  = len(hi4)  * UNIT_HIGH_RISK
cost_hi3  = len(hi3)  * UNIT_ELEVATED
cost_mid  = len(mid)  * UNIT_REMOTE
cost_low  = len(low)  * UNIT_BASE
total_cap = cost_hi4 + cost_hi3 + cost_mid + cost_low
total_maint = total * MAINTENANCE

contingency = total_cap * 0.15
total_with_cont = total_cap + contingency

print("\n" + "="*62)
print("  תקציב מיגוניות — הערכה (מחירים בש\"ח ללא מע\"מ)")
print("="*62)
col_total = 'סה"כ'
print(f"  {'קטגוריה':<30} {'יחידות':>6}  {'עלות יחידה':>12}  {col_total:>14}")
print("-"*62)
print(f"  {'כבישי גבול (risk ≥4.0)':<30} {len(hi4):>6}  {UNIT_HIGH_RISK:>12,}  {cost_hi4:>14,}")
print(f"  {'כבישי סיכון גבוה (risk 3–4)':<30} {len(hi3):>6}  {UNIT_ELEVATED:>12,}  {cost_hi3:>14,}")
print(f"  {'כבישים אזוריים (risk 2–3)':<30} {len(mid):>6}  {UNIT_REMOTE:>12,}  {cost_mid:>14,}")
print(f"  {'כבישים מהירים (risk <2)':<30} {len(low):>6}  {UNIT_BASE:>12,}  {cost_low:>14,}")
print("-"*62)
cap_label = 'עלות הון — סה"כ'
print(f"  {cap_label:<30} {total:>6}  {'':>12}  {total_cap:>14,}")
print(f"  {'רזרבה 15%':<30} {'':>6}  {'':>12}  {contingency:>14,.0f}")
total_label = 'עלות הון כולל רזרבה'
print(f"  {total_label:<30} {'':>6}  {'':>12}  {total_with_cont:>14,.0f}")
print("="*62)
print(f"  {'תחזוקה שנתית (15,000 ₪/יח׳)':<30} {total:>6}  {MAINTENANCE:>12,}  {total_maint:>14,}")
print("="*62)
print(f"\n  עלות הון (ללא רזרבה):   {total_cap/1e6:.1f} מיליון ₪")
print(f"  עלות הון (עם רזרבה 15%): {total_with_cont/1e6:.1f} מיליון ₪")
print(f"  תחזוקה שנתית:           {total_maint/1e6:.2f} מיליון ₪/שנה")

# ── Budget bar chart ───────────────────────────────────────────────────────────
fig2, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor='#F8F9FA')

# Left: cost breakdown bar
cats   = ['כבישי גבול\n(risk≥4)', 'סיכון גבוה\n(risk 3–4)', 'כבישים אזוריים\n(risk 2–3)', 'כבישים מהירים\n(risk<2)']
costs  = [cost_hi4/1e6, cost_hi3/1e6, cost_mid/1e6, cost_low/1e6]
colors = ['#c0392b', '#e67e22', '#e6b800', '#27ae60']
counts = [len(hi4), len(hi3), len(mid), len(low)]

ax1 = axes[0]
ax1.set_facecolor('#F8F9FA')
bars = ax1.bar(cats, costs, color=colors, edgecolor='white', linewidth=1.5, width=0.55)
for bar, cost, n in zip(bars, costs, counts):
    ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
             f'{cost:.1f}M ₪\n({n} יח׳)',
             ha='center', va='bottom', fontsize=9.5, fontweight='bold',
             color='#222', fontfamily='Arial Hebrew')
ax1.set_ylabel('מיליוני ₪', fontsize=11, fontfamily='Arial Hebrew')
ax1.set_title('עלות הון לפי קטגוריית סיכון', fontsize=13, fontweight='bold',
              fontfamily='Arial Hebrew', pad=12)
ax1.set_ylim(0, max(costs)*1.35)
ax1.yaxis.grid(True, linestyle='--', linewidth=0.6, color='#DDD')
ax1.set_axisbelow(True)
for spine in ['top','right']: ax1.spines[spine].set_visible(False)
for tick in ax1.get_xticklabels(): tick.set_fontfamily('Arial Hebrew')

# Right: total summary bar (capex vs contingency vs annual maintenance ×5yr)
ax2 = axes[1]
ax2.set_facecolor('#F8F9FA')
summary_labels = ['עלות הון\nבסיסית', 'רזרבה 15%', 'תחזוקה\n5 שנים', 'סה"כ\n(הון+רזרבה)']
summary_vals   = [total_cap/1e6, contingency/1e6, total_maint*5/1e6, total_with_cont/1e6]
summary_colors = ['#2980b9', '#e74c3c', '#8e44ad', '#1a5276']
bars2 = ax2.bar(summary_labels, summary_vals, color=summary_colors,
                edgecolor='white', linewidth=1.5, width=0.55)
for bar, val in zip(bars2, summary_vals):
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
             f'{val:.1f}M ₪', ha='center', va='bottom',
             fontsize=10.5, fontweight='bold', color='#222', fontfamily='Arial Hebrew')
ax2.set_ylabel('מיליוני ₪', fontsize=11, fontfamily='Arial Hebrew')
ax2.set_title('סיכום תקציבי', fontsize=13, fontweight='bold',
              fontfamily='Arial Hebrew', pad=12)
ax2.set_ylim(0, max(summary_vals)*1.3)
ax2.yaxis.grid(True, linestyle='--', linewidth=0.6, color='#DDD')
ax2.set_axisbelow(True)
for spine in ['top','right']: ax2.spines[spine].set_visible(False)
for tick in ax2.get_xticklabels(): tick.set_fontfamily('Arial Hebrew')

fig2.suptitle(f'הערכת תקציב: {total} מיגוניות בכבישים בין-עירוניים — תקן 5 דקות',
              fontsize=14, fontweight='bold', fontfamily='Arial Hebrew', y=1.01)

note = (f'הנחות: מיגונית ל-6 אנשים | עלות יחידה 400,000–520,000 ₪ | תחזוקה 15,000 ₪/שנה | '
        f'מחירים ללא מע"מ | רזרבה 15% לחריגות')
fig2.text(0.5, -0.02, note, ha='center', fontsize=8.5, color='#555',
          fontfamily='Arial Hebrew')

plt.tight_layout(pad=2.0)
plt.savefig(OUTPUT_BUDGET, dpi=180, format='jpeg', bbox_inches='tight',
            pil_kwargs={'quality': 92})
print(f"\nBudget chart saved: {OUTPUT_BUDGET}")
plt.close()
