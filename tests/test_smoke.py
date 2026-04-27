"""Baseline smoke tests against the demo feed."""
from __future__ import annotations

from gtfs2geojson import convert


def _routes(geo: dict) -> list[dict]:
    return [f for f in geo["features"] if f["geometry"]["type"] != "Point"]


def _stops(geo: dict) -> list[dict]:
    return [f for f in geo["features"] if f["geometry"]["type"] == "Point"]


def test_demo_zip_converts(demo_zip):
    geo = convert(demo_zip)
    assert geo["type"] == "FeatureCollection"
    routes = _routes(geo)
    stops = _stops(geo)
    assert {f["properties"]["route_id"] for f in routes} == {"B1", "M1", "T1"}
    assert {f["properties"]["stop_id"] for f in stops} == {"s1", "s2", "s3", "s4", "s5", "s6"}


def test_demo_dir_converts(demo_dir):
    """A directory source should match the zip source."""
    geo = convert(demo_dir)
    assert len(_routes(geo)) == 3
    assert len(_stops(geo)) == 6


def test_metro_uses_stop_sequence_reconstruction(demo_zip):
    """M1 has no shape_id — its geometry must be reconstructed from stop_times."""
    geo = convert(demo_zip)
    m1 = next(f for f in _routes(geo) if f["properties"]["route_id"] == "M1")
    assert m1["properties"]["shape_source"] == "stop_sequence"
    assert m1["properties"]["mode"] == "Metro"


def test_mode_filter(demo_zip):
    geo = convert(demo_zip, modes=["Bus"])
    rids = {f["properties"]["route_id"] for f in _routes(geo)}
    assert rids == {"B1"}


def test_bbox_filter_drops_far_routes(demo_zip):
    """Bbox covering only the airport should keep B1 and drop M1/T1."""
    geo = convert(demo_zip, bbox=(23.94, 37.93, 23.96, 37.94))
    rids = {f["properties"]["route_id"] for f in _routes(geo)}
    assert "B1" in rids
    assert "T1" not in rids


def test_no_stops_flag(demo_zip):
    geo = convert(demo_zip, include_stops=False)
    assert _stops(geo) == []
