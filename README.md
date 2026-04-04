# Road Shelter Placement — Israel

Optimal placement of road shelters (מיגוניות) on Israeli roads using the **Gonzalez Farthest-First (k-center)** algorithm.

## Live Map

Open [index.html](index.html) locally, or visit the GitHub Pages URL after enabling Pages in repo settings.

## What it does

- Fetches motorway, trunk, and primary road geometry from OpenStreetMap (Overpass API)
- Filters to **pre-1967 sovereign Israel** only (excludes West Bank, Golan, Gaza)
- Builds a road-network graph with junction cross-edges
- Runs **Gonzalez k-center** (1985) to place the minimum number of shelters such that every road point is within the time limit of a shelter:
  - Standard roads: **5-minute** access
  - Jerusalem (west of Green Line): **3-minute** access
  - Junction/interchange nodes get a placement preference bonus
- Post-placement deduplication removes shelters within 2.5 km of each other

### Results

| Metric | Value |
|--------|-------|
| Network | 5,210 km |
| Shelters placed | **336** |
| Max travel time | 4.99 min |
| Min shelter spacing | 2.52 km |
| Budget estimate | ~205M NIS (incl. 15% contingency) |

### Risk tiers

| Color | Road type | Speed | Shelter gap |
|-------|-----------|-------|------------|
| 🔴 Red | Border / Gaza envelope | 70 km/h | 11.7 km |
| 🟠 Orange | High-risk regional | 80 km/h | 13.3 km |
| 🟡 Yellow | Primary roads | 90 km/h | 15.0 km |
| 🟢 Green | Motorways / expressways | 110 km/h | 18.3 km |

## Files

| File | Description |
|------|-------------|
| `index.html` | Pre-generated interactive map (Folium + MarkerCluster) |
| `optimize_shelters.py` | Full pipeline: OSM fetch → graph → Gonzalez → maps + HTML |
| `quality_analysis.py` | QA report: close pairs, NN distribution, region breakdown |
| `requirements.txt` | Python dependencies |

## Setup

```bash
pip install -r requirements.txt
python optimize_shelters.py
```

On first run the script fetches road data from Overpass API (~2 min) and saves a local cache (`osm_roads_cache.pkl`). Subsequent runs use the cache.

The background map image (`Israeli Roads.jpg`) is not included in the repo. The schematic map and interactive HTML are generated without it.

## Algorithm reference

> Gonzalez, T.F. (1985). Clustering to minimize the maximum intercluster distance. *Theoretical Computer Science*, 38, 293–306.

Greedy 2-approximation for the k-center problem: place each new shelter at the node currently farthest from any existing shelter. Runs in O(k · E log V) time via repeated Dijkstra.

## Publishing on GitHub Pages

1. Push this repo to GitHub
2. Go to **Settings → Pages → Deploy from branch → `main` / `/ (root)`**
3. Your map is live at `https://YOUR_USERNAME.github.io/REPO_NAME/`
