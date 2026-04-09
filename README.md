# Israel Highway Shelter Placement — Project Documentation

## Overview

This project identifies optimal roadside shelter placements on Israeli highways,
prioritizing routes near the Lebanon and Gaza borders. It models wartime traffic
to estimate required shelter capacities, scores each placement by composite risk,
and produces interactive HTML maps and a budget Excel workbook.

---

## Prerequisites

```
pip install folium openpyxl
```

Python 3.9+ required. All other dependencies are standard library.

---

## Input Data

| File | Description |
|------|-------------|
| `road_segments_enriched.csv` | Highway segments with AADT, speed, highway type, midpoint coordinates |
| `alert_areas_geocoded.csv` | Alert counts per city/town since Oct 7, 2023, with geocoded lat/lon |
| `alerts_raw_since_oct7.csv` | Raw alert log (used upstream) |
| `road_segments.csv` | Base OSM road segment export |

The pipeline also relies on two intermediate pickle files generated during earlier
OSM-fetching runs (not checked in):
- `shelter_points_priority.pkl` — raw Gonzalez placement candidates
- `osm_roads_traffic_cache.pkl` — OSM road node cache

---

## Pipeline Order

Run scripts in this order to regenerate all outputs from scratch:

```
1. run_priority_placement.py        → shelter_points_priority.pkl
2. shelter_priority_pipeline.py     → shelters_priority_final.csv / .html
3. shelter_capacity.py              → shelters_with_capacity.csv
4. export_final_placements.py       → shelters_final_placements.csv
5. shelter_capacity_map.py          → shelters_map.html
6. create_budget_excel_v2.py        → shelter_budget_v2.xlsx
7. alerts_geographic_map.py         → alerts_geographic_map.html   (independent)
```

Scripts 1–2 require the OSM pickle files. Scripts 3–7 only need the CSV files.

---

## Script Descriptions

### `run_priority_placement.py`
Runs the Gonzalez k-center algorithm on OSM road nodes inside 1967 Israel to
find shelter candidates that minimize worst-case travel time. Priority zones
(north border, Gaza envelope) are seeded first.

### `shelter_priority_pipeline.py`
Post-processes raw placements: deduplication (min 2.5 km between shelters),
urban relocation (moves shelters away from city centres onto nearby rural road
segments), composite scoring, and final CSV/map export.

### `filter_shelters_borders.py`
Seven-layer geographic filter enforcing 1967 Green Line borders. Can be run as
a script to filter any shelter CSV in-place. Imported by all other scripts.

### `shelter_capacity.py`
Assigns each shelter a suggested capacity (6 / 12 / 20 people) using
rank-based assignment (30% / 30% / 40% by estimated wartime people in
catchment). Writes `shelters_with_capacity.csv`.

### `export_final_placements.py`
Applies the strict border filter one final time and exports
`shelters_final_placements.csv` — the canonical output used by the map and
budget scripts.

### `shelter_capacity_map.py`
Interactive Folium map. Markers colored by composite risk score; size by
capacity tier. Includes MarkerCluster, popups with full shelter details, and
a risk-score legend.

### `create_budget_excel_v2.py`
Generates a Hebrew RTL Excel workbook with per-shelter detail, summary
statistics, zone breakdowns, and a 10-year cost projection.

### `alerts_geographic_map.py`
Standalone choropleth map of Israel colored by rocket/missile/drone alert
density since Oct 7, 2023. Uses inverse-distance-weighted (IDW) interpolation
to fill a fine geographic grid with no blank cells.

---

## Outputs

| File | Description |
|------|-------------|
| `shelters_priority_final.csv` | All scored shelter candidates (pre-capacity) |
| `shelters_with_capacity.csv` | Candidates with AADT-based capacity estimates |
| `shelters_final_placements.csv` | Final 319 shelters (border-filtered, capacity assigned) |
| `shelters_map.html` | Interactive risk-score map |
| `shelter_budget_v2.xlsx` | Budget workbook (Hebrew, RTL) |
| `alerts_geographic_map.html` | Alert density choropleth since Oct 7, 2023 |

---

## Assumptions

### Shelter Placement Algorithm
- **Algorithm**: Gonzalez k-center (greedy farthest-point) on OSM road nodes.
- **Travel time standard**: 5 minutes maximum drive time to a shelter (uniform
  for north border and Gaza envelope zones in the final model).
- **Deduplication**: Shelters within 2.5 km of each other are merged.
- **Urban relocation**: Shelters placed inside city boundaries (within 2.5 km of
  a city centroid with ≥ 400 alerts) are moved to the nearest rural point on the
  same road ≥ 1.0 km away.

### Geographic Filtering
- All placements are filtered to remain inside Israel's **1967 Green Line**
  (pre-Six-Day-War borders). The West Bank, Gaza Strip, and Golan Heights are
  excluded.
- The filter uses a 7-layer rule stack combining bounding box, point-in-polygon
  (West Bank / Gaza polygons), and custom rule lines for known boundary gaps
  (Bethlehem/Hebron corridor, Arava valley, Jenin district, Eilat/Aqaba strip).

### Capacity Modeling
- **Wartime traffic**: 10% of normal AADT remains on roads during conflict.
- **Peak hour factor**: 9% of daily traffic (standard Israeli road planning).
- **Occupancy**: 1.3 persons per vehicle (wartime travel is mostly solo).
- **Alert windows**:
  - Within 15 km of the Lebanon or Gaza border → **4 minutes (240 s)**
  - All other areas → **5 minutes (300 s)**
- **Catchment radius**: `speed_kmh × (alert_seconds / 3600)` in each direction.
- **Capacity tiers**: 6 / 12 / 20 people assigned by traffic rank
  (bottom 30% → 6p, next 30% → 12p, top 40% → 20p).
- **Speed**: Road `maxspeed` tag used where available; fallback by highway type
  (motorway 100, trunk 90, primary 80, secondary 70 km/h).

### Risk Scoring
- **Composite score** = 0.6 × normalized alert density (Mar–Apr 2026, 15 km radius)
  + 0.4 × border proximity score.
- **Border proximity**: linearly decays from 1.0 (on the border) to 0.0 at 50 km.
  Based on distance to Lebanon and Gaza border polylines.
- Alerts used for scoring: rocket / missile / drone alerts reported by Pikud HaOref
  for March and April 2026.

### Alert Density Map
- Source: all Pikud HaOref alerts since October 7, 2023 (start of current war).
- **Grid resolution**: 0.05° ≈ 5.5 km per cell.
- **Fill method**: every grid cell inside Israel is assigned an alert index via
  inverse-distance-weighted (IDW) average of the 5 nearest geocoded cities
  (weight = 1 / (distance_km + 0.01)).
- **Color scale**: 8-bin percentile-based YlOrRd scheme (thresholds set
  dynamically from the actual distribution of blended values).

### Budget
- **Unit costs** (one-time construction): 6p = ₪73,000 | 12p = ₪100,000 | 20p = ₪150,000
- **Annual maintenance**: 2% of capital cost per year.
- **10-year cost** = capital + 10 × annual maintenance.

---

## Border Filter Quick Reference

To check or re-filter any shelter CSV against the 1967 borders:

```bash
python filter_shelters_borders.py shelters_final_placements.csv
```

The script backs up the original file before overwriting.
