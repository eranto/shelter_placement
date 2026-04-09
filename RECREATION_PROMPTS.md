# How to Recreate This Project — Prompt Guide

This document lists the approximate sequence of prompts used to build the
Israel Highway Shelter Placement project. You can use these as a starting
point to recreate or extend it with an AI coding assistant.

---

## Phase 1 — Road Data and Placement Algorithm

```
Fetch all major Israeli highway segments (motorways, trunks, primaries,
secondaries) from OpenStreetMap using the Overpass API. For each segment
extract: OSM way ID, route number (ref tag), highway type, midpoint lat/lon,
maxspeed, number of lanes, and a simplified geometry. Save to road_segments.csv.
```

```
Enrich road_segments.csv with AADT (Annual Average Daily Traffic) estimates
for Israeli highways. Use official Israeli Central Bureau of Statistics road
traffic figures where available; otherwise interpolate by highway type
(motorway ~60,000, trunk ~30,000, primary ~15,000, secondary ~5,000 vehicles/day).
Save to road_segments_enriched.csv.
```

```
Implement a Gonzalez k-center greedy placement algorithm on OSM road nodes
inside 1967 Israel. Priority zones: north border (lat > 33.05) and Gaza
envelope (lat < 31.60 and lon < 34.90). Seed priority zones first, then fill
standard zones. Target: every point on every highway is within 5 minutes'
drive of a shelter. Save placements to shelter_points_priority.pkl.
```

---

## Phase 2 — Border Filtering

```
Create filter_shelters_borders.py that filters points to remain inside
Israel's 1967 Green Line borders. Use a combination of:
- Bounding box (lat 29.45–33.35, lon 34.15–35.70)
- Point-in-polygon test for the West Bank polygon and Gaza Strip
- Lebanon/Syria border interpolation
- Golan Heights exclusion
- Jordan River / Dead Sea eastern shore
- Arava valley Israel–Jordan border formula
- Sinai/Egypt border interpolation
Expose in_1967_israel(lat, lon), strict_in_israel(lat, lon), and
filter_segment(seg) for use by other scripts.
```

---

## Phase 3 — Pipeline: Dedup, Urban Relocation, Scoring

```
Write shelter_priority_pipeline.py that:
1. Loads raw placements from shelter_points_priority.pkl
2. Deduplicates: remove any shelter within 2.5 km of a higher-ranked one
3. Relocates urban shelters: if a shelter is within 2.5 km of a city with
   400+ alerts, find the nearest rural node on the same road ≥ 1 km away
4. Re-deduplicates after relocation
5. Scores each shelter: composite = 50% normalized nearby alerts (Mar–Apr 2026,
   15 km radius) + 50% border proximity (max effect at 50 km from Lebanon or Gaza)
6. Exports shelters_priority_final.csv and a Folium HTML map
```

---

## Phase 4 — Capacity Modeling

```
Write shelter_capacity.py that assigns each shelter a suggested capacity
based on wartime road traffic:
- Wartime traffic = 10% of normal AADT
- Peak hour = 9% of daily AADT
- Alert window: 4 minutes if within 15 km of Lebanon or Gaza border, else 5 minutes
- Catchment: vehicles driveable in the alert window at road speed, both directions
- People = vehicles × 1.3 persons/vehicle
- Capacity tiers: 6 / 12 / 20 people, assigned by rank (30% / 30% / 40%)
Save to shelters_with_capacity.csv.
```

```
Write export_final_placements.py that applies the strict 1967 border filter
to shelters_with_capacity.csv and exports shelters_final_placements.csv with
columns: rank, lat, lon, road, zone, composite_score, nearby_alerts_marapr2026,
highway_type, road_speed_kmh, catchment_per_dir_km, aadt_normal, aadt_wartime,
estimated_people_in_catchment, suggested_capacity, alert_seconds.
```

---

## Phase 5 — Maps

```
Write shelter_capacity_map.py that creates a Folium interactive map of
shelters_final_placements.csv. Color markers by composite risk score
(5 bins: very low blue-grey → very high red). Size markers by capacity
(6p=small, 12p=medium, 20p=large). Add a MarkerCluster, popups with full
shelter details, and a legend. Save to shelters_map.html.
```

```
Write alerts_geographic_map.py that creates a choropleth map of Israel
colored by total rocket/missile/drone alert count since October 7, 2023.
Load geocoded alert areas from alert_areas_geocoded.csv. Divide Israel into
a 0.05° grid (~5.5 km cells). For each cell inside 1967 Israel, compute an
IDW-blended alert value from the 5 nearest cities (weight = 1/(distance+0.01)).
Use a dynamic 8-bin percentile-based YlOrRd color scale. Add tooltips showing
the blended alert index and nearest city. Save to alerts_geographic_map.html.
```

---

## Phase 6 — Budget Excel

```
Write create_budget_excel_v2.py that generates a Hebrew RTL Excel workbook
from shelters_final_placements.csv with:
- Per-shelter detail sheet with all columns
- Summary sheet: total shelters, capacity distribution, cost per tier
- Zone breakdown (North border / Gaza envelope / Standard)
- Unit costs: 6p=₪73,000, 12p=₪100,000, 20p=₪150,000
- 10-year cost = capital + 10 × 2% annual maintenance
Use openpyxl; set Hebrew RTL direction on all sheets; use formatted number
cells for currency and counts.
```

---

## Common Refinement Prompts

These were used iteratively to improve the project:

```
Some shelters are outside Israel's 1967 borders. Ranks [X, Y, Z] appear to be
in Jordan / the West Bank. Tighten the filter in filter_shelters_borders.py
to exclude them, then re-run shelter_capacity.py and export_final_placements.py.
```

```
Rearrange capacity tiers so that low-traffic shelters get 6 people, the majority
get 12 people, and high-traffic get 20 people. Use rank-based assignment:
bottom 30% → 6p, next 30% → 12p, top 40% → 20p.
```

```
Make the alert density map finer — use a 0.05° grid instead of 0.25°, and fill
all cells inside Israel using IDW interpolation from the 5 nearest cities so
there are no blank gaps in the center and south of the country.
```

```
The map should show composite risk score as the color (not capacity). Use 5
color bins from blue-grey (very low) to red (very high), with the score formula:
0.6 × normalized alerts + 0.4 × border proximity.
```

---

## Notes

- Always filter outputs through `filter_shelters_borders.py` after any
  pipeline step that produces lat/lon coordinates.
- When adding new capacity tiers or cost figures, update both
  `shelter_capacity.py` (STANDARD_SIZES) and `create_budget_excel_v2.py`
  (CAPACITY_COST) together.
- The OSM pickle files (`shelter_points_priority.pkl`,
  `osm_roads_traffic_cache.pkl`) are large and not tracked in git. They
  must be regenerated by running `run_priority_placement.py` and the OSM
  fetch step respectively.
