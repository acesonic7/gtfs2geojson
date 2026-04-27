# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-04-27

### Added
- **Mode legend** in the preview map (bottom-right): each mode with its
  colour swatch and route count.
- **Summary sidebar** in the preview map (bottom-left, collapsible via the
  native `<details>` element): feed title, agencies, route counts by mode,
  stop count, and total network length.
- **Stop search** via `folium.plugins.Search` keyed on `stop_name`. The
  search box appears top-left of the map.
- **Configurable tiles**: `tiles=` parameter on `render()` and `--tiles`
  CLI flag. Aliases `positron` (default), `osm`, `dark_matter`. Any other
  string is forwarded straight to Folium.
- 13 new tests in `test_preview.py` (skipped automatically when the
  `[preview]` extra is not installed). Suite is now **75 passing**.

### Changed
- Stops are now rendered as a `folium.GeoJson` layer (with `CircleMarker`
  styling) rather than a `MarkerCluster`. This is what makes them
  searchable. Visual appearance is essentially unchanged — small white dots
  with grey outline, hidden by default in the layer control.
- Removed the floating title marker from the corner of the map; the same
  information now lives in the sidebar header.

### Fixed
- **Bug #11**: removed the redundant `attr=` on `folium.Map(...)` — for
  built-in tile names (`cartodbpositron` etc.) Folium provides the
  attribution itself, and the manually-supplied attribution was being
  ignored.

## [0.4.0] - 2026-04-27

### Added
- **`--format {geojson,geojsonseq}` / `write(..., format=)`** — emit either a
  single ``FeatureCollection`` (default) or RFC 8142 record-separated GeoJSON
  with one ``Feature`` per record. Compatible with `tippecanoe` and
  `ogr2ogr`'s `GeoJSONSeq` driver.
- **`--list-modes`** and **`--list-agencies`** introspection subcommands.
  Read just `routes.txt` (+ `agency.txt`) and print mode / agency labels with
  per-item route counts. Mutually exclusive with each other.
- **`--json`** modifier for the introspection commands — switches the output
  from aligned columns to a machine-readable JSON list.
- New public API: `gtfs2geojson.list_modes(source)` and
  `gtfs2geojson.list_agencies(source)`.
- 19 new tests across `test_format.py`, `test_introspect.py`, and
  `test_cli.py`. Suite is now **62 passing** on Python 3.12.

### Changed
- `agency.txt` is now read **before** `routes.txt`. The route's
  `agency_id` field on each output feature carries the *resolved* agency id —
  either as written, or filled in from the sole agency when the GTFS
  sole-agency rule applies (see Bug #4 below).

### Fixed
- **Bug #4**: when a feed has exactly one agency, routes whose `agency_id`
  is empty are now correctly attributed to that agency. Previously they
  were dropped by `--agency` filters and bucketed under the empty string in
  agency listings.

## [0.3.0] - 2026-04-27

### Added
- **`--date YYYYMMDD` / `service_date=`** filter — keep only trips whose
  `service_id` is active on the given calendar day. Combines `calendar.txt`
  weekday rules (within `start_date`/`end_date`) with `calendar_dates.txt`
  exceptions (`exception_type=1` adds, `=2` removes). Accepts `YYYYMMDD`,
  `YYYY-MM-DD`, or a `datetime.date`.
- **`--simplify TOLERANCE` / `simplify_tolerance=`** — Ramer-Douglas-Peucker
  line simplification, tolerance in degrees of lon/lat (~111 km × cos(lat)
  per degree). Endpoints preserved. `length_km` is recomputed *after*
  simplification so it always matches the emitted geometry.
- 23 new tests covering date normalisation, calendar/calendar_dates rules,
  RDP edge cases, post-simplify length consistency, and the bug-fix paths
  below. Suite is now 43 passing.

### Changed
- Reconstruction is now built for **every** route that has trips with
  `stop_times` entries, and applied as a fallback whenever the shapes-derived
  geometry is empty — not only when the route had no `shape_id` at all.
- Stops are read into an unfiltered `all_stops` dict; the bbox-filtered
  output set is derived from it. This lets reconstruction draw on stops
  outside the bbox so the resulting line can then be evaluated against the
  same any-vertex-in-bbox rule that shapes use.

### Fixed
- **Bug #2**: a route whose only `shape_id` resolves to fewer than two valid
  points is no longer dropped silently — it now falls back to stop-sequence
  reconstruction (when `reconstruct_missing_shapes=True`).
- **Bug #3**: bbox treatment is now consistent for shapes vs reconstructed
  lines. Both use the "keep the whole line if any vertex is in the bbox"
  rule. Previously reconstruction was implicitly clipped to in-bbox stops,
  which could produce lines that wouldn't have been emitted from a
  shapes-derived path covering the same geometry.

## [0.2.0] - 2026-04-27

### Added
- **Per-route stats** on every route feature: `n_trips`, `n_stops`, and
  `length_km` (great-circle distance summed over all shape variants).
- **Stops carry routes**: each stop feature now includes `route_ids` (sorted
  list of routes serving it) and `modes` (distinct mode labels among those
  routes).
- **`feature_type: "route"`** on route features for symmetry with stops.
- **`--keep-orphan-stops` flag** (and `keep_orphan_stops=` parameter) to retain
  stops not served by any kept trip. Default is to drop orphans, with an info
  message to stderr noting the count.
- **`tests/`** directory with pytest fixtures (`demo_zip`, `demo_dir`,
  `demo_files`, `feed_factory`) and 20 tests covering smoke / stats /
  stop-route linkage / warnings.
- **`CHANGELOG.md`** (this file).
- **Warning** to stderr when `routes.txt` is missing or empty.

### Changed
- Single pass over `stop_times.txt` now powers reconstruction, per-route stop
  counts, and the stop→routes index. Eliminates the duplicate scan that v0.1.0
  performed for reconstruction.
- `shape_source` logic rewritten using an explicit `used_reconstruction` flag
  rather than the previous compound boolean expression.
- `_parse_bbox` returns an explicit 4-tuple rather than `tuple(parts)` (drops
  the `# type: ignore`).

### Fixed
- Reconstruction no longer skipped silently when a route's only `shape_id`
  resolves to a shape with fewer than 2 points; the route now falls back to
  stop-sequence reconstruction (when allowed).

## [0.1.0] - 2026-04-27

Initial release. Source corresponds to the contents of `gtfs2geojson.tar.gz`.

### Added
- `convert(source, ...)` — GTFS (zip or directory) → GeoJSON `FeatureCollection`.
- `write(geojson, path)` — write to file or stdout.
- `gtfs2geojson` console script (CLI) with `--mode`, `--agency`, `--bbox`,
  `--no-stops`, `--no-reconstruct`, `--preview`, `--title` flags.
- Mode-aware styling for basic + extended (HVT) GTFS route types.
- Geometry reconstruction from `stop_times` when `shapes.txt` is absent.
- Optional Folium preview map under the `[preview]` extra.

[Unreleased]: https://github.com/acesonic7/gtfs2geojson/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/acesonic7/gtfs2geojson/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/acesonic7/gtfs2geojson/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/acesonic7/gtfs2geojson/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/acesonic7/gtfs2geojson/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/acesonic7/gtfs2geojson/releases/tag/v0.1.0
