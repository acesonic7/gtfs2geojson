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
- **Filters**: by mode (`--mode Bus`), by agency (`--agency OASA`), by bounding box (`--bbox w,s,e,n`)
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
    include_stops=True,
)
write(geo, "feed.geojson")
render(geo, "preview.html", title="Athens core network")
```

## Output schema

Each route feature carries:

| Property | Description |
|---|---|
| `route_id`, `route_short_name`, `route_long_name` | from `routes.txt` |
| `route_type` | original GTFS integer |
| `mode` | human label (`Bus`, `Metro`, `Tram`, `Ferry`, …) |
| `route_color`, `route_text_color` | hex strings, with mode-based defaults |
| `agency_id`, `agency_name` | joined from `agency.txt` |
| `headsigns` | up to 6 distinct headsigns concatenated with `|` |
| `shape_source` | `"shapes.txt"` or `"stop_sequence"` (reconstructed) |

Stop features carry `feature_type: "stop"`, `stop_id`, `stop_name`, `stop_code`.

## Why?

Converting GTFS to GeoJSON should be a one-liner. Most existing options either:

- require Postgres/PostGIS (too heavy for a quick visualisation),
- assume `shapes.txt` is always present (it isn't — many metros, trams, and older feeds skip it),
- or output undecorated geometries with no styling hooks.

`gtfs2geojson` aims to be the boring, dependable, do-one-thing tool you can plug into a Makefile or notebook.

## Limitations / non-goals

- No service-day filtering — `calendar.txt` and `calendar_dates.txt` are ignored. Every route with at least one trip is included.
- No frequency or schedule data on the output.
- No realtime (GTFS-RT) support — schedule feeds only.

If you need any of the above, [`gtfs_kit`](https://github.com/mrcagney/gtfs_kit) and [`partridge`](https://github.com/remix/partridge) are excellent.

## License

MIT.
