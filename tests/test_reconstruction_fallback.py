"""Bugs #2 and #3 (v0.3): reconstruction fallback + consistent bbox treatment."""
from __future__ import annotations

from gtfs2geojson import convert


def _routes(geo: dict) -> dict[str, dict]:
    return {f["properties"]["route_id"]: f
            for f in geo["features"] if f["geometry"]["type"] != "Point"}


def test_invalid_shape_falls_back_to_reconstruction(demo_files, feed_factory):
    """Bug #2: a route whose shape resolves to fewer than 2 valid points
    should fall back to stop_times reconstruction, not be silently dropped."""
    files = dict(demo_files)
    # B1's shape sh_b1 now has only one valid row.
    files["shapes.txt"] = (
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "sh_b1,37.9755,23.7348,1\n"   # only one point — invalid as a line
        "sh_t1,37.9300,23.7100,1\nsh_t1,37.9250,23.7250,2\n"
    )
    feed = feed_factory(files)
    geo = convert(feed)
    routes = _routes(geo)
    # Before the fix, B1 would be dropped — now it reconstructs from t_b1's
    # stop sequence (s1 → s4).
    assert "B1" in routes
    assert routes["B1"]["properties"]["shape_source"] == "stop_sequence"


def test_reconstructed_line_subject_to_bbox_rule(demo_files, feed_factory):
    """Bug #3: reconstruction now uses ALL stops (not just bbox-filtered ones),
    and the resulting line is then accepted/rejected by the same any-vertex-in-bbox
    rule that shapes use. So a route whose stops STRADDLE the bbox should appear,
    even if some stops fall outside."""
    files = dict(demo_files)
    # M1 has no shape; its trip t_m1 visits s1, s2, s3.
    # Place a bbox covering only s1 (Centre): (23.733, 37.974, 23.737, 37.976).
    feed = feed_factory(files)
    geo = convert(feed, bbox=(23.733, 37.974, 23.737, 37.976))
    routes = _routes(geo)
    # M1 should appear because s1 is in the bbox — even though s2, s3 aren't.
    assert "M1" in routes
    assert routes["M1"]["properties"]["shape_source"] == "stop_sequence"


def test_reconstructed_line_dropped_when_no_vertex_in_bbox(demo_files, feed_factory):
    """The flip side: if NONE of the reconstructed stops fall in the bbox,
    the route is dropped — same as the shapes-derived rule."""
    files = dict(demo_files)
    feed = feed_factory(files)
    # Bbox far from all M1 stops.
    geo = convert(feed, bbox=(0.0, 0.0, 1.0, 1.0))
    assert "M1" not in _routes(geo)
