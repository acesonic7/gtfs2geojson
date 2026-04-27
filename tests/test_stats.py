"""Per-route stats added in v0.2: n_trips, n_stops, length_km."""
from __future__ import annotations

import math

import pytest

from gtfs2geojson import convert
from gtfs2geojson.converter import _haversine_km, _line_length_km


def _routes_by_id(geo: dict) -> dict[str, dict]:
    return {f["properties"]["route_id"]: f
            for f in geo["features"] if f["geometry"]["type"] != "Point"}


def test_haversine_known_distance():
    # Athens (Syntagma) → Thessaloniki (Aristotelous) — published GC distance ~ 301 km.
    d = _haversine_km(23.7361, 37.9755, 22.9444, 40.6325)
    assert 295 < d < 305


def test_line_length_zero_for_single_point():
    assert _line_length_km([[0.0, 0.0]]) == 0.0


def test_line_length_additive():
    pts = [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    expected = _haversine_km(0, 0, 0, 1) + _haversine_km(0, 1, 1, 1)
    assert math.isclose(_line_length_km(pts), expected)


def test_each_route_carries_stats(demo_zip):
    geo = convert(demo_zip)
    routes = _routes_by_id(geo)
    assert set(routes) == {"B1", "M1", "T1"}
    for rid, f in routes.items():
        p = f["properties"]
        assert p["n_trips"] >= 1, f"{rid} should have at least one trip"
        assert p["n_stops"] >= 2, f"{rid} should touch at least 2 stops"
        assert p["length_km"] > 0, f"{rid} length must be positive"
        assert p["feature_type"] == "route"


def test_n_trips_matches_trips_txt(demo_zip):
    geo = convert(demo_zip)
    routes = _routes_by_id(geo)
    # Each demo route has exactly one trip in trips.txt.
    assert routes["B1"]["properties"]["n_trips"] == 1
    assert routes["M1"]["properties"]["n_trips"] == 1
    assert routes["T1"]["properties"]["n_trips"] == 1


def test_n_stops_uses_distinct_count(demo_zip):
    geo = convert(demo_zip)
    routes = _routes_by_id(geo)
    # B1 hits {s1, s4}; M1 hits {s1, s2, s3}; T1 hits {s5, s6}.
    assert routes["B1"]["properties"]["n_stops"] == 2
    assert routes["M1"]["properties"]["n_stops"] == 3
    assert routes["T1"]["properties"]["n_stops"] == 2


def test_length_km_is_plausible_for_demo(demo_zip):
    geo = convert(demo_zip)
    routes = _routes_by_id(geo)
    # B1 spans from (23.7348, 37.9755) to (23.9468, 37.9356) — ~19 km.
    assert 15 < routes["B1"]["properties"]["length_km"] < 25
    # T1 is two adjacent coastal points — ~1-2 km.
    assert 0.5 < routes["T1"]["properties"]["length_km"] < 3
