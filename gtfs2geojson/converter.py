"""GTFS → GeoJSON conversion."""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

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


def convert(
    source: str | Path,
    *,
    modes: Iterable[str] | None = None,
    agencies: Iterable[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    include_stops: bool = True,
    reconstruct_missing_shapes: bool = True,
) -> dict:
    """Convert a GTFS feed (zip file or directory) to a GeoJSON FeatureCollection.

    Routes become MultiLineString features (one per route, all shape variants merged).
    Stops become Point features with a feature_type='stop' tag.

    Parameters
    ----------
    source : path to .zip or directory containing GTFS .txt files
    modes : optional iterable of mode labels to keep (e.g. ['Bus','Metro']). Case-insensitive.
    agencies : optional iterable of agency_id values to keep.
    bbox : optional (west, south, east, north) lon/lat filter.
    include_stops : whether to emit stop features.
    reconstruct_missing_shapes : if a route has no shapes.txt entry, build polylines
        from its stop_times sequence as a fallback.
    """
    mode_filter = {m.lower() for m in modes} if modes else None
    agency_filter = set(agencies) if agencies else None

    # ── Routes ────────────────────────────────────────────────────────────
    routes_raw = _read_csv(source, "routes.txt")
    routes: dict[str, dict] = {}
    for r in routes_raw:
        try:
            rt = int(r.get("route_type", "3"))
        except ValueError:
            rt = 3
        mode_label, default_color = ROUTE_TYPE_MAP.get(rt, ("Other", "#616161"))
        if mode_filter and mode_label.lower() not in mode_filter:
            continue
        if agency_filter and r.get("agency_id", "") not in agency_filter:
            continue
        routes[r["route_id"]] = {
            "route_id": r["route_id"],
            "agency_id": r.get("agency_id", ""),
            "route_short_name": r.get("route_short_name", ""),
            "route_long_name": r.get("route_long_name", ""),
            "route_type": rt,
            "mode": mode_label,
            "route_color": _normalise_colour(r.get("route_color", ""), default_color),
            "route_text_color": _normalise_colour(r.get("route_text_color", ""), "#FFFFFF"),
        }

    # Agency lookup for nicer attribution
    agency_name_by_id: dict[str, str] = {}
    for a in _read_csv(source, "agency.txt"):
        agency_name_by_id[a.get("agency_id", "")] = a.get("agency_name", "")

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

    # ── Trips → route↔shape map + headsigns ───────────────────────────────
    route_shapes: dict[str, set[str]] = defaultdict(set)
    route_headsigns: dict[str, set[str]] = defaultdict(set)
    trip_to_route: dict[str, str] = {}
    for t in _read_csv(source, "trips.txt"):
        rid = t.get("route_id", "")
        if rid not in routes:
            continue
        trip_to_route[t["trip_id"]] = rid
        sid = t.get("shape_id", "")
        if sid:
            route_shapes[rid].add(sid)
        hs = t.get("trip_headsign", "")
        if hs:
            route_headsigns[rid].add(hs)

    # ── Stops ─────────────────────────────────────────────────────────────
    stops: dict[str, dict] = {}
    for s in _read_csv(source, "stops.txt"):
        try:
            lat = float(s["stop_lat"])
            lon = float(s["stop_lon"])
        except (KeyError, ValueError):
            continue
        if not _in_bbox(lon, lat, bbox):
            continue
        stops[s["stop_id"]] = {
            "stop_id": s["stop_id"],
            "stop_name": s.get("stop_name", ""),
            "stop_code": s.get("stop_code", ""),
            "lat": lat,
            "lon": lon,
        }

    # ── Optional shape reconstruction from stop_times ────────────────────
    reconstructed: dict[str, list[tuple[float, float]]] = {}
    if reconstruct_missing_shapes:
        routes_missing = {rid for rid in routes if not route_shapes.get(rid)}
        if routes_missing:
            # Build trip → ordered list of stop_ids
            trip_stop_seq: dict[str, list[tuple[int, str]]] = defaultdict(list)
            for st in _read_csv(source, "stop_times.txt"):
                tid = st.get("trip_id", "")
                rid = trip_to_route.get(tid)
                if rid not in routes_missing:
                    continue
                try:
                    seq = int(st["stop_sequence"])
                except (KeyError, ValueError):
                    continue
                trip_stop_seq[tid].append((seq, st["stop_id"]))
            # Pick one representative trip per route (longest stop sequence)
            best_trip: dict[str, str] = {}
            for tid, seq in trip_stop_seq.items():
                rid = trip_to_route.get(tid)
                if rid is None:
                    continue
                if rid not in best_trip or len(seq) > len(trip_stop_seq[best_trip[rid]]):
                    best_trip[rid] = tid
            for rid, tid in best_trip.items():
                seq = sorted(trip_stop_seq[tid])
                pts = []
                for _, sid in seq:
                    if sid in stops:
                        pts.append((stops[sid]["lon"], stops[sid]["lat"]))
                if len(pts) >= 2:
                    reconstructed[rid] = pts

    # ── Build features ────────────────────────────────────────────────────
    features: list[dict] = []

    for rid, info in routes.items():
        lines: list[list[list[float]]] = []
        for sid in sorted(route_shapes.get(rid, [])):
            pts = shapes_by_id.get(sid, [])
            if len(pts) >= 2:
                line = [[lon, lat] for _, lat, lon in pts]
                if bbox is None or any(_in_bbox(x, y, bbox) for x, y in line):
                    lines.append(line)
        if not lines and rid in reconstructed:
            lines.append([[x, y] for x, y in reconstructed[rid]])
        if not lines:
            continue
        props = dict(info)
        props["agency_name"] = agency_name_by_id.get(info["agency_id"], "")
        props["headsigns"] = " | ".join(sorted(route_headsigns.get(rid, []))[:6])
        props["shape_source"] = "shapes.txt" if rid not in reconstructed or route_shapes.get(rid) else "stop_sequence"
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "MultiLineString" if len(lines) > 1 else "LineString",
                "coordinates": lines if len(lines) > 1 else lines[0],
            },
        })

    if include_stops:
        for sid, s in stops.items():
            features.append({
                "type": "Feature",
                "properties": {
                    "feature_type": "stop",
                    "stop_id": s["stop_id"],
                    "stop_name": s["stop_name"],
                    "stop_code": s["stop_code"],
                },
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            })

    return {"type": "FeatureCollection", "features": features}


def write(geojson: dict, path: str | Path | None) -> None:
    """Write GeoJSON to disk (or stdout if path is '-' or None)."""
    text = json.dumps(geojson, ensure_ascii=False)
    if path in (None, "-"):
        print(text)
    else:
        Path(path).write_text(text, encoding="utf-8")
