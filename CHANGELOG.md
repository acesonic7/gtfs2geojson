# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/acesonic7/gtfs2geojson/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/acesonic7/gtfs2geojson/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/acesonic7/gtfs2geojson/releases/tag/v0.1.0
