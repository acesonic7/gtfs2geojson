# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `tests/` directory with shared `conftest.py` fixtures (`demo_zip`, `demo_dir`,
  `demo_files`, `feed_factory`) and baseline smoke tests for the demo feed.
- `CHANGELOG.md` (this file).

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

[Unreleased]: https://github.com/acesonic7/gtfs2geojson/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/acesonic7/gtfs2geojson/releases/tag/v0.1.0
