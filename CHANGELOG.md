# Changelog

All notable changes to the shelter placement analysis are documented here.

---

## [2.0.0] — 2026-04-06

### Added
- **`israel_1967_filter.py`** — Geographic filter that restricts all analysis to Israel's 1967 Green Line borders. Uses point-in-polygon tests (ray-casting) for:
  - West Bank (17-vertex Green Line polygon)
  - Gaza Strip (6-vertex polygon)
  - Lebanon border (interpolated lat limit by longitude)
  - Golan Heights (two-threshold longitude check: >35.67 for lat 32.65–32.88; >35.62 for lat >32.88, reflecting the Jordan River boundary north of the Sea of Galilee)
  - Sinai / Egypt (Rafah–Eilat line)
  - Jordan River / Arava valley (interpolated line from Dead Sea to Eilat)
  - 15/15 sanity tests passing

- **`run_priority_placement.py`** — Full Gonzalez farthest-first placement re-run with:
  - 1967 border filter applied at segment load time (14,750 → 11,519 segments; 6,097 km)
  - Zone definitions: Jerusalem 3.0 min, standard 5.0 min
  - Final border purge after placement (removes any shelter outside 1967 Israel)
  - Outputs `shelter_points_priority.pkl` (819 shelters pre-dedup)

- **`shelter_priority_pipeline.py`** — End-to-end pipeline from raw placements to final map:
  - 2.5 km post-dedup (819 → 426 shelters)
  - Urban relocation: moves shelters within 2.5 km of cities (≥400 alerts) to rural road nodes; 73 relocated, 20 kept urban
  - **Composite ranking**: 50% Mar–Apr 2026 alert density + 50% border proximity score (Lebanon/Gaza fence, 50 km decay)
  - Interactive Folium map with cluster markers, popup details, and legend
  - CSV export with all scoring components
  - Outputs: `shelters_priority_final.html`, `shelters_priority_final.csv`

- **`shelter_urban_relocate.py`** — Standalone urban relocation script; outputs `shelters_rural_deduped.csv`

- **`shelter_marapr2026_ranking.py`** — Standalone Mar–Apr 2026 alert ranking; outputs `shelters_marapr2026_deduped.csv`, `shelters_marapr2026_alert_ranked.html`

- **`export_datasets.py`** — Exports shelter analysis to CSV (base, AADT-ranked, alert-ranked, combined)

- **`export_source_datasets.py`** — Exports raw source data to CSV (alert areas, road segments)

- **`WORKFLOW.md`** — Full pipeline documentation with step-by-step description, parameters, design decisions, and reproduction instructions

### Changed
- **`shelter_alert_ranking.py`** — Added 2.5 km dedup step after loading pkl (was missing, causing shelter count inflation)
- **`road_shelters_traffic.py`** — Updated to use traffic-weighted graph with lane capacity and speed data

### Data
- **`shelters_priority_final.csv`** — 385 final shelter locations ranked by composite score (alerts + border proximity), all within 1967 Israel
- **`shelters_priority_final.html`** — Interactive map of 385 shelters
- **`alert_areas_geocoded.csv`** — 850 Pikud HaOref alert areas with geocoded coordinates (73.9% coverage)
- **`alert_areas_all.csv`** — All 1,571 alert area names with total alert counts
- **`road_segments.csv`** — 11,519 OSM road segments within 1967 Israel (6,097 km)

---

## [1.0.0] — 2026-04-04

### Initial Release
- Basic Gonzalez k-center placement on Israeli road network
- OSM road data fetched via Overpass API and cached
- Missile alert density scoring using Oct 7 2023 – present alert data
- Interactive Folium map output (`index.html`)
- Budget analysis Excel file (`budget_shelters.xlsx`)
- Quality analysis script (`quality_analysis.py`)
- Optimization script (`optimize_shelters.py`)
