"""Command-line entry point: `python -m gtfs2geojson` or `gtfs2geojson`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import convert, write


def _parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be 'west,south,east,north'")
    return parts[0], parts[1], parts[2], parts[3]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="gtfs2geojson",
        description="Convert a GTFS feed (zip or directory) to GeoJSON.",
    )
    p.add_argument("source", help="Path to a GTFS .zip file or directory")
    p.add_argument("-o", "--output", default="-",
                   help="Output GeoJSON path (default: stdout)")
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
    p.add_argument("--title", default=None,
                   help="Title shown in the preview map (defaults to source filename)")

    args = p.parse_args(argv)

    if not Path(args.source).exists():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 2

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

    write(geojson, args.output)

    if args.preview:
        from .preview import render
        render(geojson, args.preview, title=args.title or Path(args.source).name)
        print(f"preview: {args.preview}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
