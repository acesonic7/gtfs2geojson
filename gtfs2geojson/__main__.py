"""Command-line entry point: `python -m gtfs2geojson` or `gtfs2geojson`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .converter import convert, list_agencies, list_modes, write


def _parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be 'west,south,east,north'")
    return parts[0], parts[1], parts[2], parts[3]


def _print_modes(counts: dict[str, int], as_json: bool) -> None:
    if as_json:
        rows = [{"mode": m, "n_routes": n} for m, n in
                sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
        sys.stdout.write(json.dumps(rows, ensure_ascii=False) + "\n")
        return
    if not counts:
        return
    width = max(len(m) for m in counts)
    print(f"{'Mode'.ljust(width)}  Routes")
    for mode, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{mode.ljust(width)}  {n:>6}")


def _print_agencies(rows: list[dict], as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(rows, ensure_ascii=False) + "\n")
        return
    if not rows:
        return
    id_w = max(len(r["agency_id"] or "(none)") for r in rows)
    name_w = max(len(r["agency_name"] or "") for r in rows)
    id_w = max(id_w, len("agency_id"))
    name_w = max(name_w, len("agency_name"))
    print(f"{'agency_id'.ljust(id_w)}  {'agency_name'.ljust(name_w)}  Routes")
    for r in sorted(rows, key=lambda x: (-x["n_routes"], x["agency_id"])):
        aid = r["agency_id"] or "(none)"
        print(f"{aid.ljust(id_w)}  {r['agency_name'].ljust(name_w)}  {r['n_routes']:>6}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="gtfs2geojson",
        description="Convert a GTFS feed (zip or directory) to GeoJSON.",
    )
    p.add_argument("source", help="Path to a GTFS .zip file or directory")
    p.add_argument("-o", "--output", default="-",
                   help="Output path (default: stdout)")
    p.add_argument("--format", choices=("geojson", "geojsonseq"), default="geojson",
                   help="Output format: 'geojson' (default, single FeatureCollection) "
                        "or 'geojsonseq' (RFC 8142, one Feature per record — for "
                        "tippecanoe / ogr2ogr's GeoJSONSeq driver).")
    p.add_argument("--preview", metavar="HTML",
                   help="Also write an interactive Folium preview map to this path")
    p.add_argument("--mode", action="append", default=None,
                   help="Keep only routes of this mode (repeatable). "
                        "E.g. --mode Bus --mode Metro")
    p.add_argument("--agency", action="append", default=None,
                   help="Keep only routes from this agency_id (repeatable)")
    p.add_argument("--bbox", type=_parse_bbox, default=None,
                   help="Filter to bounding box: west,south,east,north (lon/lat)")
    p.add_argument("--no-stops", action="store_true",
                   help="Skip emitting stop point features")
    p.add_argument("--no-reconstruct", action="store_true",
                   help="Do not reconstruct missing route shapes from stop sequences")
    p.add_argument("--keep-orphan-stops", action="store_true",
                   help="Keep stop features even when no kept trip touches them "
                        "(default: drop orphans)")
    p.add_argument("--date", default=None,
                   help="Only keep trips active on this calendar date "
                        "(YYYYMMDD or YYYY-MM-DD). Combines calendar.txt weekday "
                        "rules with calendar_dates.txt exceptions.")
    p.add_argument("--simplify", type=float, default=None, metavar="TOLERANCE",
                   help="Simplify polylines using Ramer-Douglas-Peucker with this "
                        "tolerance in degrees of lon/lat (e.g. 0.0001 ≈ 10 m). "
                        "Endpoints are preserved.")
    introspect = p.add_mutually_exclusive_group()
    introspect.add_argument("--list-modes", action="store_true",
                            help="List the modes present in routes.txt with route "
                                 "counts and exit. Other conversion flags are ignored.")
    introspect.add_argument("--list-agencies", action="store_true",
                            help="List the agencies present (with route counts) and exit.")
    p.add_argument("--json", action="store_true",
                   help="Emit machine-readable JSON for --list-modes / --list-agencies.")
    p.add_argument("--title", default=None,
                   help="Title shown in the preview map (defaults to source filename)")

    args = p.parse_args(argv)

    if not Path(args.source).exists():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 2

    if args.list_modes:
        _print_modes(list_modes(args.source), as_json=args.json)
        return 0
    if args.list_agencies:
        _print_agencies(list_agencies(args.source), as_json=args.json)
        return 0

    geojson = convert(
        args.source,
        modes=args.mode,
        agencies=args.agency,
        bbox=args.bbox,
        include_stops=not args.no_stops,
        reconstruct_missing_shapes=not args.no_reconstruct,
        keep_orphan_stops=args.keep_orphan_stops,
        service_date=args.date,
        simplify_tolerance=args.simplify,
    )

    n_routes = sum(1 for f in geojson["features"] if f["geometry"]["type"] != "Point")
    n_stops = sum(1 for f in geojson["features"] if f["geometry"]["type"] == "Point")
    print(f"converted: {n_routes} route features, {n_stops} stop features",
          file=sys.stderr)

    write(geojson, args.output, format=args.format)

    if args.preview:
        from .preview import render
        render(geojson, args.preview, title=args.title or Path(args.source).name)
        print(f"preview: {args.preview}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
