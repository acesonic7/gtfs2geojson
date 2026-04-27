"""Stops carry route_ids/modes; orphan-stop dropping (v0.2)."""
from __future__ import annotations

from gtfs2geojson import convert


def _stops_by_id(geo: dict) -> dict[str, dict]:
    return {f["properties"]["stop_id"]: f
            for f in geo["features"] if f["geometry"]["type"] == "Point"}


def test_stops_carry_route_ids(demo_zip):
    geo = convert(demo_zip)
    stops = _stops_by_id(geo)
    # s1 is shared by B1 and M1 (both serve it in stop_times).
    assert stops["s1"]["properties"]["route_ids"] == ["B1", "M1"]
    # s4 is only on B1 (Airport).
    assert stops["s4"]["properties"]["route_ids"] == ["B1"]
    # s5/s6 only on T1.
    assert stops["s5"]["properties"]["route_ids"] == ["T1"]


def test_stops_carry_modes(demo_zip):
    geo = convert(demo_zip)
    stops = _stops_by_id(geo)
    assert stops["s1"]["properties"]["modes"] == ["Bus", "Metro"]
    assert stops["s4"]["properties"]["modes"] == ["Bus"]
    assert stops["s5"]["properties"]["modes"] == ["Tram"]


def test_orphan_stops_dropped_by_default(demo_files, feed_factory):
    files = dict(demo_files)
    # Add an orphan stop not referenced anywhere in stop_times.
    files["stops.txt"] = files["stops.txt"] + "orphan,Lonely,37.0,23.0\n"
    feed = feed_factory(files)
    geo = convert(feed)
    stops = _stops_by_id(geo)
    assert "orphan" not in stops


def test_keep_orphan_stops_flag(demo_files, feed_factory):
    files = dict(demo_files)
    files["stops.txt"] = files["stops.txt"] + "orphan,Lonely,37.0,23.0\n"
    feed = feed_factory(files)
    geo = convert(feed, keep_orphan_stops=True)
    stops = _stops_by_id(geo)
    assert "orphan" in stops
    assert stops["orphan"]["properties"]["route_ids"] == []
    assert stops["orphan"]["properties"]["modes"] == []


def test_no_stop_times_falls_back_to_keeping_all(demo_files, feed_factory):
    """Without stop_times.txt every stop would look orphan; we keep all of them."""
    files = dict(demo_files)
    del files["stop_times.txt"]
    feed = feed_factory(files)
    geo = convert(feed)
    stops = _stops_by_id(geo)
    # All 6 demo stops should still come through.
    assert set(stops) == {"s1", "s2", "s3", "s4", "s5", "s6"}
    # Route_ids/modes are present but empty (no link info available).
    assert stops["s1"]["properties"]["route_ids"] == []
