# Road Shelter Placement — Workflow Documentation

## Overview

This project computes optimal roadside bomb-shelter (מיגונית) placements across Israel's 1967 Green Line borders. The algorithm ensures every point on the Israeli road network is within N minutes of a shelter, with tighter time standards near conflict zones.

---

## Final Outputs

| File | Description |
|------|-------------|
| `shelters_priority_final.html` | Interactive Folium map of 401 final shelter locations |
| `shelters_priority_final.csv` | CSV of all 401 shelters with coordinates, zone, road name, alert score |
| `shelter_points_priority.pkl` | Intermediate: raw 838-shelter Gonzalez output (pre-dedup) |

---

## Pipeline Steps

### Step 1 — OSM Road Data Collection
**Script:** `road_shelters_traffic.py` (initial), then extended by `run_priority_placement.py`  
**Prompt / intent:** Fetch all road segments in Israel from OpenStreetMap and build a travel-time graph.

- Downloads road segments via Overpass API and caches them in `osm_roads_traffic_cache.pkl` (14,750 segments)
- Each segment carries: geometry (lat/lon waypoints), highway type, lane count, max speed, and a route reference name
- Road speeds are derived from highway type and max speed tag:
  - Motorway: 70–130 km/h, Trunk: 70 km/h, Primary: 80 km/h, Secondary: 90 km/h, default: 110 km/h

---

### Step 2 — 1967 Green Line Filter
**Script:** `israel_1967_filter.py`  
**Prompt / intent:** "Make sure all analysis is done within the borders of 1967 Israel (Green Line), excluding West Bank, Gaza, Golan Heights, and Sinai."

Filters road segments (and individual shelter candidates) to those within pre-1967 Israeli sovereign territory:

- **Lebanon border**: lat > 33.07°N (coast) interpolated to 33.27°N (east)
- **Golan Heights**: lat > 32.65° AND lon > 35.67° (captured 1967, annexed 1981 — excluded)
- **Jordan River / West Bank east**: lat 31–32.65°, lon > 35.57°
- **Arava valley**: lat 29.56–31.0°, border interpolated from Eilat (29.56, 35.00) to Dead Sea (31.05, 35.42)
- **West Bank (Green Line)**: point-in-polygon test against a 17-vertex clockwise polygon
- **Gaza Strip**: point-in-polygon test against a 6-vertex polygon
- **Sinai / Egypt**: lat < 31.24°, west of Rafah–Eilat line

Result: 14,750 raw OSM segments → 11,519 within 1967 Israel (6,097 km of roads)

---

### Step 3 — Road Graph Construction
**Script:** `run_priority_placement.py`  
**Prompt / intent:** Build a graph on which Dijkstra shortest paths represent travel time.

- Interpolates each road geometry at 0.5 km intervals → road nodes
- Deduplicates coincident nodes (same location rounded to 4 decimal places)
- Adds junction edges (weight 0) between nodes from different roads within 0.1 km
- Result: **15,923 unique demand nodes**, ~20,623 total edges

---

### Step 4 — Zone Assignment
**Script:** `run_priority_placement.py`  
**Prompt / intent:** "Give precedence to areas near the north border and Gaza strip. Reduce the time-to-alarm there to 4.5 minutes."

Each node is assigned a time-limit zone:

| Zone | Condition | Time Standard |
|------|-----------|---------------|
| Jerusalem | lat 31.72–31.87, lon 34.92–35.18 | 3.0 minutes |
| North border | lat > 33.05° | 4.5 minutes |
| Gaza envelope | lat < 31.60° AND lon < 34.90° | 4.5 minutes |
| Standard (everywhere else) | — | 5.0 minutes |

Zone breakdown of the 15,923 nodes:
- Jerusalem: 507 nodes
- Priority (north + Gaza): 2,412 nodes
- Standard: 13,004 nodes

---

### Step 5 — Gonzalez Farthest-First Placement
**Script:** `run_priority_placement.py`  
**Prompt / intent:** Place the minimum number of shelters so every road node is within its zone's time limit.

Algorithm (k-center / Gonzalez):
1. Start at the highest-risk node
2. Run Dijkstra from the current shelter set to update each node's distance to nearest shelter
3. Score each uncovered node: `score = dist_to_nearest / time_limit + junction_bonus + traffic_bonus`
4. Add the highest-scoring node as the next shelter
5. Repeat until all nodes are covered (distance ≤ zone time limit)

Node score bonuses:
- Junction bonus: +0.30 if the node connects multiple roads
- Traffic/capacity bonus: +0.10 × (cap_weight − 1.0), scaled by lane capacity

Result: **855 shelters** placed (standard=686, priority=127, jerusalem=42)  
Max travel time: **4.88 minutes**

---

### Step 6 — Border Purge
**Script:** `run_priority_placement.py` (final step before saving)  
**Prompt / intent:** Remove any shelter whose final coordinates fall outside 1967 Israel.

Even after filtering road segments at load time, Gonzalez can select nodes near polygon boundaries that fail the more precise point test. A final sweep removes these.

Result: 855 → **838 shelters** after purge (17 removed)  
Saved to: `shelter_points_priority.pkl`

---

### Step 7 — Post-Deduplication
**Script:** `shelter_priority_pipeline.py`  
**Prompt / intent:** "Make sure there aren't shelters too close to each other."

Gonzalez optimises for coverage, which can place multiple shelters very close together on parallel routes. Apply a 2.5 km minimum-distance dedup:

1. Sort shelters by (cap_weight, risk) descending — prefer high-capacity / high-risk placements
2. Greedily keep each shelter only if it is ≥ 2.5 km from all already-kept shelters

Result: 838 → **442 shelters** after dedup

---

### Step 8 — Urban Relocation
**Script:** `shelter_priority_pipeline.py` (calls logic from `shelter_urban_relocate.py`)  
**Prompt / intent:** "Try to minimize shelters near residential areas — they already have existing infrastructure. Move them to places further from residential areas."

Cities with ≥ 400 missile alerts are treated as "urban" reference points. Any shelter within 2.5 km of such a city is relocated to the nearest road node on the same route that is > 2.5 km from any city.

Result (of 442 shelters):
- Rural, unchanged: **349**
- Relocated to rural node: **73**
- Kept urban (no rural alternative on route): **20**

After re-dedup (relocation can create new duplicates): **401 final shelters**

Zone breakdown: North border=10, Gaza envelope=70, Standard=321

---

### Step 9 — Mar–Apr 2026 Alert Scoring
**Script:** `shelter_priority_pipeline.py`  
**Prompt / intent:** "Rerun the shelter analysis but look only at March–April 2026."

Each shelter is scored by summing missile alert counts for all cities within 15 km:

- Alert data source: `israel_alerts.csv` (github.com/dleshem/israel-alerts-data)
- Geocoding: `geocoded_cities.json` (850 entries, 73.9% coverage after manual patching of Nominatim results)
- Time window: March 1 – April 30 2026 (~393,200 alert-area instances)

Shelters are ranked from highest to lowest nearby alert density. This ranking determines deployment priority (Shelter #1 is deployed first).

---

### Step 10 — Map and CSV Export
**Script:** `shelter_priority_pipeline.py`  
**Output:** `shelters_priority_final.html`, `shelters_priority_final.csv`

The interactive HTML map (Folium) shows:
- Shelter markers colored by alert density (red = very high, grey = minimal)
- Marker size proportional to alert score
- Popup with: rank, road name, zone, alert count, risk score, lane capacity
- Layer toggle between shelter clusters and alert city reference points

The CSV includes columns: rank, lat, lon, road_name, zone, risk, cap_weight, nearby_alerts

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Gonzalez (k-center) over clustering | Guarantees worst-case coverage; every node is within the time limit by construction |
| Zone-specific time limits | Tighter standards in conflict-exposed zones (3–4.5 min vs 5 min) reflect real alert response times |
| 1967 Green Line filter | Analysis scoped to Israeli sovereign territory per original project requirements |
| 2.5 km dedup | Avoids redundant shelters on parallel/overlapping routes; consistent threshold across all scripts |
| Urban relocation | Road shelters complement, not duplicate, existing urban shelter infrastructure |
| Mar–Apr 2026 alert window | Heavy escalation in this period (339,264 events in March alone) makes it the most relevant operational window |
| 15 km alert catchment radius | Balances hyper-local precision against geocoding coverage gaps |

---

## File Map

```
Shelter Placement 2006/
├── israel_1967_filter.py          # Green Line border filter (step 2)
├── run_priority_placement.py      # Gonzalez placement with priority zones (steps 3–6)
├── shelter_priority_pipeline.py   # Dedup → relocate → score → export (steps 7–10)
├── shelter_urban_relocate.py      # Standalone urban relocation script
├── shelter_marapr2026_ranking.py  # Standalone Mar-Apr 2026 ranking
├── shelter_alert_ranking.py       # All-time alert ranking (baseline)
├── export_datasets.py             # Export shelter analysis to CSV
├── export_source_datasets.py      # Export raw source data to CSV
├── road_shelters_traffic.py       # Original OSM fetch + graph build
├── osm_roads_traffic_cache.pkl    # Cached OSM road segments (14,750)
├── shelter_points_priority.pkl    # Gonzalez output: 838 shelters (post-purge)
├── shelters_priority_final.html   # Final interactive map (401 shelters)
└── shelters_priority_final.csv    # Final shelter list with alert rankings
```

---

## Reproducing from Scratch

```bash
# 1. Fetch OSM data (requires internet, takes ~10 min)
python road_shelters_traffic.py

# 2. Run priority placement (takes ~5 min)
python run_priority_placement.py

# 3. Run full pipeline (takes ~2 min)
python shelter_priority_pipeline.py
```

All intermediate files are cached — re-running individual steps is safe.
