"""GTFS → GeoJSON conversion."""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

# GTFS route_type → (human label, default hex colour)
# Covers basic + extended route types (Hierarchical Vehicle Type / HVT).
ROUTE_TYPE_MAP: dict[int, tuple[str, str]] = {
    0: ("Tram", "#E91E63"),
    1: ("Metro", "#D32F2F"),
    2: ("Rail", "#5D4037"),
    3: ("Bus", "#1976D2"),
    4: ("Ferry", "#0097A7"),
    5: ("CableTram", "#795548"),
    6: ("AerialLift", "#7B1FA2"),
    7: ("Funicular", "#6D4C41"),
    11: ("Trolleybus", "#388E3C"),
    12: ("Monorail", "#455A64"),
    # extended (commonly seen)
    100: ("Rail", "#5D4037"),
    101: ("HighSpeedRail", "#B71C1C"),
    102: ("LongDistanceRail", "#5D4037"),
    109: ("SuburbanRail", "#6D4C41"),
    200: ("Coach", "#1565C0"),
    400: ("UrbanRail", "#D32F2F"),
    401: ("Metro", "#D32F2F"),
    402: ("Underground", "#D32F2F"),
    700: ("Bus", "#1976D2"),
    701: ("RegionalBus", "#1976D2"),
    702: ("ExpressBus", "#0D47A1"),
    704: ("LocalBus", "#1976D2"),
    715: ("DemandBus", "#1E88E5"),
    800: ("Trolleybus", "#388E3C"),
    900: ("Tram", "#E91E63"),
    1000: ("Ferry", "#0097A7"),
    1300: ("AerialLift", "#7B1FA2"),
    1400: ("Funicular", "#6D4C41"),
    1700: ("Other", "#616161"),
}


def _open_text(source: str | Path, name: str) -> io.TextIOWrapper | None:
    """Open a GTFS text file from either a directory or a zip archive."""
    p = Path(source)
    if p.is_dir():
        f = p / name
        if not f.exists():
            return None
        return open(f, "r", encoding="utf-8-sig", newline="")
    # assume zip
    with zipfile.ZipFile(p) as zf:
        # case-insensitive lookup
        names = {n.lower(): n for n in zf.namelist()}
        if name.lower() not in names:
            return None
        # read the whole entry into memory and wrap as text
        data = zf.read(names[name.lower()]).decode("utf-8-sig")
    return io.StringIO(data)


def _read_csv(source: str | Path, name: str) -> list[dict]:
    f = _open_text(source, name)
    if f is None:
        return []
    with f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _normalise_colour(hex_str: str, fallback: str) -> str:
    h = (hex_str or "").lstrip("#").strip()
    if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
        return f"#{h.upper()}"
    return fallback


def _in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


_EARTH_RADIUS_KM = 6371.0088


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance between two lon/lat points, in kilometres."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _line_length_km(coords: list[list[float]]) -> float:
    """Sum of haversine distances between consecutive [lon, lat] points."""
    total = 0.0
    for i in range(1, len(coords)):
        x1, y1 = coords[i - 1]
        x2, y2 = coords[i]
        total += _haversine_km(x1, y1, x2, y2)
    return total


def _normalise_gtfs_date(value: str | _dt.date) -> str:
    """Coerce a date input into the GTFS ``YYYYMMDD`` form.

    Accepts ``datetime.date``/``datetime.datetime``, ``YYYYMMDD``, or ISO
    ``YYYY-MM-DD``. Raises ``ValueError`` for anything else.
    """
    if isinstance(value, _dt.datetime):
        value = value.date()
    if isinstance(value, _dt.date):
        return value.strftime("%Y%m%d")
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():
        _dt.datetime.strptime(s, "%Y%m%d")  # validates
        return s
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return _dt.datetime.strptime(s, "%Y-%m-%d").strftime("%Y%m%d")
    raise ValueError(f"unrecognised date format: {value!r} (expected YYYYMMDD or YYYY-MM-DD)")


_WEEKDAY_COLUMNS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _active_services_on(source: str | Path, gtfs_date: str) -> set[str]:
    """Return the set of ``service_id`` values active on the given GTFS date.

    Combines ``calendar.txt`` (weekday flags within ``start_date``/``end_date``)
    with ``calendar_dates.txt`` exceptions: ``exception_type=1`` adds, ``=2`` removes.
    Either file may be absent — the rules degrade gracefully.
    """
    target = _dt.datetime.strptime(gtfs_date, "%Y%m%d").date()
    weekday_col = _WEEKDAY_COLUMNS[target.weekday()]

    active: set[str] = set()
    for c in _read_csv(source, "calendar.txt"):
        sid = c.get("service_id", "")
        if not sid:
            continue
        try:
            start = _dt.datetime.strptime(c.get("start_date", ""), "%Y%m%d").date()
            end = _dt.datetime.strptime(c.get("end_date", ""), "%Y%m%d").date()
        except ValueError:
            continue
        if not (start <= target <= end):
            continue
        if c.get(weekday_col, "0") == "1":
            active.add(sid)

    for x in _read_csv(source, "calendar_dates.txt"):
        if x.get("date", "") != gtfs_date:
            continue
        sid = x.get("service_id", "")
        et = x.get("exception_type", "")
        if et == "1":
            active.add(sid)
        elif et == "2":
            active.discard(sid)
    return active


def _rdp(points: list[list[float]], epsilon: float) -> list[list[float]]:
    """Iterative Ramer-Douglas-Peucker line simplification.

    ``epsilon`` is a perpendicular-distance tolerance in degrees of lon/lat.
    Endpoints are always preserved. Returns ``points`` unchanged if it has fewer
    than three vertices or ``epsilon <= 0``.

    Rough degree → metre conversion at common latitudes (1° lat ≈ 111 km;
    1° lon at 40°N ≈ 85 km). So ``epsilon=0.0001`` ≈ 8-11 metres.
    """
    n = len(points)
    if n < 3 or epsilon <= 0:
        return points
    keep = [False] * n
    keep[0] = True
    keep[-1] = True
    stack: list[tuple[int, int]] = [(0, n - 1)]
    eps_sq = epsilon * epsilon
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        ax, ay = points[i]
        bx, by = points[j]
        dx = bx - ax
        dy = by - ay
        seg_len_sq = dx * dx + dy * dy
        max_d_sq = -1.0
        max_idx = -1
        for k in range(i + 1, j):
            px, py = points[k]
            if seg_len_sq == 0.0:
                d_sq = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
                projx = ax + t * dx
                projy = ay + t * dy
                d_sq = (px - projx) ** 2 + (py - projy) ** 2
            if d_sq > max_d_sq:
                max_d_sq = d_sq
                max_idx = k
        if max_d_sq > eps_sq:
            keep[max_idx] = True
            stack.append((i, max_idx))
            stack.append((max_idx, j))
    return [points[k] for k in range(n) if keep[k]]


def convert(
    source: str | Path,
    *,
    modes: Iterable[str] | None = None,
    agencies: Iterable[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    include_stops: bool = True,
    reconstruct_missing_shapes: bool = True,
    keep_orphan_stops: bool = False,
    service_date: str | _dt.date | None = None,
    simplify_tolerance: float | None = None,
) -> dict:
    """Convert a GTFS feed (zip file or directory) to a GeoJSON FeatureCollection.

    Routes become MultiLineString features (one per route, all shape variants merged).
    Stops become Point features with ``feature_type='stop'`` and the list of
    ``route_ids``/``modes`` that serve them.

    Parameters
    ----------
    source : path to .zip or directory containing GTFS .txt files
    modes : optional iterable of mode labels to keep (e.g. ['Bus','Metro']). Case-insensitive.
    agencies : optional iterable of agency_id values to keep.
    bbox : optional (west, south, east, north) lon/lat filter. Lines are kept if
        any vertex falls in the box; the geometry is not clipped.
    include_stops : whether to emit stop features.
    reconstruct_missing_shapes : if a route's shapes are missing or empty, fall back
        to building polylines from its stop_times sequence.
    keep_orphan_stops : if True, emit stop features even when no kept trip touches
        them. Defaults to False (orphan stops are dropped). Has no effect when
        ``stop_times.txt`` is missing — in that case all stops are kept.
    service_date : if set, only keep trips whose ``service_id`` is active on the
        given GTFS calendar date. Accepts ``datetime.date`` or a string in
        ``YYYYMMDD`` / ``YYYY-MM-DD`` form.
    simplify_tolerance : if set and > 0, simplify each polyline with the
        Ramer-Douglas-Peucker algorithm using this tolerance in degrees of
        lon/lat. Endpoints are preserved. ``length_km`` is computed *after*
        simplification so it always matches the emitted geometry.
    """
    mode_filter = {m.lower() for m in modes} if modes else None
    agency_filter = set(agencies) if agencies else None
    service_filter: set[str] | None = None
    if service_date is not None:
        gtfs_date = _normalise_gtfs_date(service_date)
        service_filter = _active_services_on(source, gtfs_date)
        if not service_filter:
            print(
                f"warning: no services active on {gtfs_date}; output will contain "
                "no route features",
                file=sys.stderr,
            )

    # ── Agencies (read first so the sole-agency fallback below works) ────
    # GTFS allows routes.agency_id to be omitted when the feed has exactly
    # one agency; in that case the route implicitly belongs to it.
    agency_name_by_id: dict[str, str] = {}
    for a in _read_csv(source, "agency.txt"):
        aid = a.get("agency_id", "")
        if aid:
            agency_name_by_id[aid] = a.get("agency_name", "")
    sole_agency_id = next(iter(agency_name_by_id)) if len(agency_name_by_id) == 1 else None

    # ── Routes ────────────────────────────────────────────────────────────
    routes_raw = _read_csv(source, "routes.txt")
    if not routes_raw:
        print(
            "warning: no routes found in routes.txt (file missing or empty); "
            "output will contain no route features",
            file=sys.stderr,
        )
    routes: dict[str, dict] = {}
    for r in routes_raw:
        try:
            rt = int(r.get("route_type", "3"))
        except ValueError:
            rt = 3
        mode_label, default_color = ROUTE_TYPE_MAP.get(rt, ("Other", "#616161"))
        if mode_filter and mode_label.lower() not in mode_filter:
            continue
        agency_id = r.get("agency_id", "") or (sole_agency_id or "")
        if agency_filter and agency_id not in agency_filter:
            continue
        routes[r["route_id"]] = {
            "route_id": r["route_id"],
            "agency_id": agency_id,
            "route_short_name": r.get("route_short_name", ""),
            "route_long_name": r.get("route_long_name", ""),
            "route_type": rt,
            "mode": mode_label,
            "route_color": _normalise_colour(r.get("route_color", ""), default_color),
            "route_text_color": _normalise_colour(r.get("route_text_color", ""), "#FFFFFF"),
        }

    # ── Shapes ────────────────────────────────────────────────────────────
    shapes_by_id: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for s in _read_csv(source, "shapes.txt"):
        try:
            seq = int(s["shape_pt_sequence"])
            lat = float(s["shape_pt_lat"])
            lon = float(s["shape_pt_lon"])
        except (KeyError, ValueError):
            continue
        shapes_by_id[s["shape_id"]].append((seq, lat, lon))
    for sid in shapes_by_id:
        shapes_by_id[sid].sort()

    # ── Trips → route↔shape map + headsigns + per-route trip set ─────────
    route_shapes: dict[str, set[str]] = defaultdict(set)
    route_headsigns: dict[str, set[str]] = defaultdict(set)
    route_trips: dict[str, set[str]] = defaultdict(set)
    trip_to_route: dict[str, str] = {}
    for t in _read_csv(source, "trips.txt"):
        rid = t.get("route_id", "")
        if rid not in routes:
            continue
        if service_filter is not None and t.get("service_id", "") not in service_filter:
            continue
        tid = t.get("trip_id", "")
        if tid:
            trip_to_route[tid] = rid
            route_trips[rid].add(tid)
        sid = t.get("shape_id", "")
        if sid:
            route_shapes[rid].add(sid)
        hs = t.get("trip_headsign", "")
        if hs:
            route_headsigns[rid].add(hs)

    # ── Stops ─────────────────────────────────────────────────────────────
    # all_stops is unfiltered — used for shape reconstruction so a route whose
    # stops sit just outside the bbox can still produce a candidate line that
    # then goes through the same any-vertex-in-bbox rule shapes use.
    # `stops` is the bbox-filtered subset that actually gets emitted.
    all_stops: dict[str, dict] = {}
    for s in _read_csv(source, "stops.txt"):
        try:
            lat = float(s["stop_lat"])
            lon = float(s["stop_lon"])
        except (KeyError, ValueError):
            continue
        all_stops[s["stop_id"]] = {
            "stop_id": s["stop_id"],
            "stop_name": s.get("stop_name", ""),
            "stop_code": s.get("stop_code", ""),
            "lat": lat,
            "lon": lon,
        }
    stops: dict[str, dict] = {
        sid: s for sid, s in all_stops.items() if _in_bbox(s["lon"], s["lat"], bbox)
    }

    # ── Single pass over stop_times.txt ──────────────────────────────────
    # Builds, in one walk:
    #   * trip_stop_seq    — ordered (seq, stop_id) per trip, used for reconstruction
    #   * route_stop_set   — distinct stop_ids touched by each route (n_stops stat)
    #   * stop_to_routes   — reverse index: which routes serve each stop
    #
    # Skipping this pass entirely is only valid when no consumer needs it; today
    # at least one of (stats / stops carry routes / reconstruction) always does.
    trip_stop_seq: dict[str, list[tuple[int, str]]] = defaultdict(list)
    route_stop_set: dict[str, set[str]] = defaultdict(set)
    stop_to_routes: dict[str, set[str]] = defaultdict(set)
    saw_any_stop_time = False
    for st in _read_csv(source, "stop_times.txt"):
        saw_any_stop_time = True
        tid = st.get("trip_id", "")
        rid = trip_to_route.get(tid)
        if rid is None:
            continue
        sid = st.get("stop_id", "")
        if sid:
            route_stop_set[rid].add(sid)
            stop_to_routes[sid].add(rid)
        try:
            seq = int(st["stop_sequence"])
        except (KeyError, ValueError):
            continue
        if sid:
            trip_stop_seq[tid].append((seq, sid))

    # ── Optional shape reconstruction from stop_times ────────────────────
    # We build a candidate reconstruction for every route that has at least one
    # trip with stop_times — not only routes whose `route_shapes` set is empty.
    # The feature loop below then uses it as a fallback whenever the
    # shapes.txt-derived `lines` list ends up empty (e.g. shape_id present but
    # the shape has < 2 valid points, or all shape vertices are outside bbox).
    reconstructed: dict[str, list[tuple[float, float]]] = {}
    if reconstruct_missing_shapes and trip_stop_seq:
        best_trip: dict[str, str] = {}
        for tid, seq in trip_stop_seq.items():
            rid = trip_to_route.get(tid)
            if rid is None:
                continue
            if rid not in best_trip or len(seq) > len(trip_stop_seq[best_trip[rid]]):
                best_trip[rid] = tid
        for rid, tid in best_trip.items():
            seq = sorted(trip_stop_seq[tid])
            pts: list[tuple[float, float]] = []
            for _, sid in seq:
                s = all_stops.get(sid)
                if s is not None:
                    pts.append((s["lon"], s["lat"]))
            if len(pts) >= 2:
                reconstructed[rid] = pts

    # ── Build features ────────────────────────────────────────────────────
    features: list[dict] = []
    do_simplify = simplify_tolerance is not None and simplify_tolerance > 0

    for rid, info in routes.items():
        lines: list[list[list[float]]] = []
        for sid in sorted(route_shapes.get(rid, [])):
            pts = shapes_by_id.get(sid, [])
            if len(pts) >= 2:
                line = [[lon, lat] for _, lat, lon in pts]
                if bbox is None or any(_in_bbox(x, y, bbox) for x, y in line):
                    lines.append(line)
        used_reconstruction = False
        if not lines and rid in reconstructed:
            line = [[x, y] for x, y in reconstructed[rid]]
            if bbox is None or any(_in_bbox(x, y, bbox) for x, y in line):
                lines.append(line)
                used_reconstruction = True
        if not lines:
            continue
        if do_simplify:
            lines = [_rdp(line, simplify_tolerance) for line in lines]  # type: ignore[arg-type]
        length_km = sum(_line_length_km(line) for line in lines)
        props = dict(info)
        props["feature_type"] = "route"
        props["agency_name"] = agency_name_by_id.get(info["agency_id"], "")
        props["headsigns"] = " | ".join(sorted(route_headsigns.get(rid, []))[:6])
        props["shape_source"] = "stop_sequence" if used_reconstruction else "shapes.txt"
        props["n_trips"] = len(route_trips.get(rid, ()))
        props["n_stops"] = len(route_stop_set.get(rid, ()))
        props["length_km"] = round(length_km, 3)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "MultiLineString" if len(lines) > 1 else "LineString",
                "coordinates": lines if len(lines) > 1 else lines[0],
            },
        })

    if include_stops:
        # If stop_times.txt was missing/empty, every stop would look orphan;
        # fall back to keeping all stops so the user gets *something* useful.
        keep_all = keep_orphan_stops or not saw_any_stop_time
        dropped_orphans = 0
        for sid, s in stops.items():
            stop_routes = sorted(stop_to_routes.get(sid, ()))
            if not stop_routes and not keep_all:
                dropped_orphans += 1
                continue
            stop_modes = sorted({routes[r]["mode"] for r in stop_routes if r in routes})
            features.append({
                "type": "Feature",
                "properties": {
                    "feature_type": "stop",
                    "stop_id": s["stop_id"],
                    "stop_name": s["stop_name"],
                    "stop_code": s["stop_code"],
                    "route_ids": stop_routes,
                    "modes": stop_modes,
                },
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            })
        if dropped_orphans:
            print(
                f"info: dropped {dropped_orphans} orphan stop(s) not served by any "
                "kept trip (use --keep-orphan-stops or keep_orphan_stops=True to retain)",
                file=sys.stderr,
            )

    return {"type": "FeatureCollection", "features": features}


_RS = "\x1e"  # ASCII Record Separator (RFC 8142 / GeoJSON-seq)


def write(geojson: dict, path: str | Path | None, *, format: str = "geojson") -> None:
    """Write a FeatureCollection to disk (or stdout if ``path`` is ``'-'`` / ``None``).

    ``format`` selects the on-disk encoding:

    * ``"geojson"`` (default) — a single ``FeatureCollection`` JSON object.
    * ``"geojsonseq"`` — RFC 8142 record-separated GeoJSON: each record is one
      ``Feature`` preceded by ``\\x1e`` and terminated by ``\\n``. Compatible
      with tippecanoe and ogr2ogr's ``GeoJSONSeq`` driver.
    """
    if format == "geojson":
        text = json.dumps(geojson, ensure_ascii=False)
        if path in (None, "-"):
            print(text)
            return
        Path(path).write_text(text, encoding="utf-8")
        return
    if format == "geojsonseq":
        parts = [
            f"{_RS}{json.dumps(f, ensure_ascii=False)}\n"
            for f in geojson.get("features", [])
        ]
        text = "".join(parts)
        if path in (None, "-"):
            sys.stdout.write(text)  # already ends with \n per record
            return
        Path(path).write_text(text, encoding="utf-8")
        return
    raise ValueError(f"unknown format: {format!r} (expected 'geojson' or 'geojsonseq')")


def list_modes(source: str | Path) -> dict[str, int]:
    """Return ``{mode_label: route_count}`` for every distinct mode in routes.txt.

    Uses the same ``ROUTE_TYPE_MAP`` collapsing that ``convert()`` does, so e.g.
    route_types 3, 700, 701, 704 all aggregate under ``"Bus"``.
    """
    counts: dict[str, int] = defaultdict(int)
    for r in _read_csv(source, "routes.txt"):
        try:
            rt = int(r.get("route_type", "3"))
        except ValueError:
            rt = 3
        mode_label, _ = ROUTE_TYPE_MAP.get(rt, ("Other", "#616161"))
        counts[mode_label] += 1
    return dict(counts)


def list_agencies(source: str | Path) -> list[dict]:
    """Return a list of ``{agency_id, agency_name, n_routes}`` records.

    Routes whose ``agency_id`` is empty are attributed to the sole agency when
    the feed has exactly one — matching the GTFS spec's implicit fallback.
    """
    agencies: dict[str, str] = {}
    for a in _read_csv(source, "agency.txt"):
        aid = a.get("agency_id", "")
        if aid:
            agencies[aid] = a.get("agency_name", "")
    sole = next(iter(agencies)) if len(agencies) == 1 else None

    counts: dict[str, int] = defaultdict(int)
    for r in _read_csv(source, "routes.txt"):
        aid = r.get("agency_id", "") or (sole or "")
        counts[aid] += 1

    rows: list[dict] = []
    for aid in sorted(counts):
        rows.append({
            "agency_id": aid,
            "agency_name": agencies.get(aid, ""),
            "n_routes": counts[aid],
        })
    return rows
