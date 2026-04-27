"""Bug fix #6: empty/missing routes.txt emits a warning."""
from __future__ import annotations

from gtfs2geojson import convert


def test_missing_routes_txt_warns(demo_files, feed_factory, capsys):
    files = dict(demo_files)
    del files["routes.txt"]
    feed = feed_factory(files)
    geo = convert(feed)
    captured = capsys.readouterr()
    assert "no routes" in captured.err.lower()
    # Output is still a valid (empty-of-routes) FeatureCollection.
    assert geo["type"] == "FeatureCollection"
    assert all(f["geometry"]["type"] == "Point" or f["geometry"]["type"] == "Point"
               for f in geo["features"]) or geo["features"] == []


def test_empty_routes_txt_warns(demo_files, feed_factory, capsys):
    files = dict(demo_files)
    files["routes.txt"] = "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    feed = feed_factory(files)
    convert(feed)
    captured = capsys.readouterr()
    assert "no routes" in captured.err.lower()
