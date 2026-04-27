# gtfs2geojson

Convert any [GTFS](https://gtfs.org/schedule/) feed (zip file or directory) into a clean, styled GeoJSON `FeatureCollection`, with an optional interactive Folium preview map.

Built for transit data folks who want a quick, dependency-light way to go from `gtfs.zip` → something they can drop into kepler.gl, QGIS, deck.gl, Mapbox, or a Leaflet/Folium map — without spinning up Postgres/PostGIS.

## Features

- **Single command, no database**: `gtfs2geojson feed.zip -o feed.geojson`
- **Reads zip or directory** GTFS sources, handles UTF-8 BOM
- **Routes as MultiLineString** features, one per `route_id` (all shape variants merged)
- **Stops as Point** features
- **Mode-aware styling** — readable labels (Bus / Metro / Tram / Ferry / Trolleybus / …) with sensible default colours, falling back from `route_color` when missing
- **Reconstructs missing geometry** from `stop_times` when a route has no entry in `shapes.txt` (common for metros/trams in older feeds)
- **Filters**: by mode (`--mode Bus`), by agency (`--agency OASA`), by bounding box (`--bbox w,s,e,n`), by **service day** (`--date 20260615`)
- **Line simplification** with Ramer-Douglas-Peucker (`--simplify 0.0001`) for smaller, faster-rendering output
- **Optional Folium preview** with per-mode toggleable layers and clustered stops
- **Extended GTFS route types** supported (HVT codes 100–1700)

## Install

```bash
pip install gtfs2geojson           # core
pip install "gtfs2geojson[preview]" # also installs folium for --preview
```

Or from source:

```bash
git clone https://github.com/acesonic7/gtfs2geojson
cd gtfs2geojson
pip install -e ".[preview]"
```

## CLI

```bash
# basic
gtfs2geojson feed.zip -o feed.geojson

# with interactive map
gtfs2geojson feed.zip -o feed.geojson --preview map.html

# filter to buses + metro inside a bbox, skip stops
gtfs2geojson feed.zip \
  --mode Bus --mode Metro \
  --bbox 23.6,37.9,23.8,38.05 \
  --no-stops \
  -o athens_core.geojson

# only trips active on a particular calendar date (combines calendar.txt
# weekday rules with calendar_dates.txt exceptions)
gtfs2geojson feed.zip --date 20260615 -o that_monday.geojson

# simplify polylines for web/mobile rendering (~10 m at most latitudes)
gtfs2geojson feed.zip --simplify 0.0001 -o feed.simplified.geojson

# feed already extracted to a directory
gtfs2geojson ./gtfs_extracted/ -o feed.geojson
```

Stream to stdout (default) for piping into other tools:

```bash
gtfs2geojson feed.zip | jq '.features | length'
```

## Python API

```python
from gtfs2geojson import convert, write
from gtfs2geojson.preview import render

geo = convert(
    "feed.zip",
    modes=["Bus", "Trolleybus"],
    bbox=(23.6, 37.9, 23.8, 38.05),
    service_date="2026-06-15",       # also accepts "20260615" or datetime.date
    simplify_tolerance=0.0001,       # ~10 m perpendicular tolerance
    include_stops=True,
)
write(geo, "feed.geojson")
render(geo, "preview.html", title="Athens core network")
```

## Output schema

Each route feature carries:

| Property | Description |
|---|---|
| `feature_type` | always `"route"` |
| `route_id`, `route_short_name`, `route_long_name` | from `routes.txt` |
| `route_type` | original GTFS integer |
| `mode` | human label (`Bus`, `Metro`, `Tram`, `Ferry`, …) |
| `route_color`, `route_text_color` | hex strings, with mode-based defaults |
| `agency_id`, `agency_name` | joined from `agency.txt` |
| `headsigns` | up to 6 distinct headsigns concatenated with `\|` |
| `shape_source` | `"shapes.txt"` or `"stop_sequence"` (reconstructed) |
| `n_trips` | number of trips serving this route |
| `n_stops` | number of distinct stops touched by any trip on this route |
| `length_km` | total network length, sum of all shape variants (haversine, km) |

Stop features carry:

| Property | Description |
|---|---|
| `feature_type` | always `"stop"` |
| `stop_id`, `stop_name`, `stop_code` | from `stops.txt` |
| `route_ids` | sorted list of routes serving this stop |
| `modes` | sorted list of distinct modes among those routes |

By default, stops not served by any kept trip are dropped — pass `--keep-orphan-stops`
(CLI) or `keep_orphan_stops=True` (Python) to retain them. If `stop_times.txt` is
absent, all stops are kept regardless.

## Why?

Converting GTFS to GeoJSON should be a one-liner. Most existing options either:

- require Postgres/PostGIS (too heavy for a quick visualisation),
- assume `shapes.txt` is always present (it isn't — many metros, trams, and older feeds skip it),
- or output undecorated geometries with no styling hooks.

`gtfs2geojson` aims to be the boring, dependable, do-one-thing tool you can plug into a Makefile or notebook.

## Limitations / non-goals

- No frequency or schedule data on the output.
- No realtime (GTFS-RT) support — schedule feeds only.

If you need any of the above, [`gtfs_kit`](https://github.com/mrcagney/gtfs_kit) and [`partridge`](https://github.com/remix/partridge) are excellent.

## License

MIT.
