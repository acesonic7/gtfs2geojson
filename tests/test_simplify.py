"""Line simplification via --simplify / simplify_tolerance (v0.3)."""
from __future__ import annotations

from gtfs2geojson import convert
from gtfs2geojson.converter import _rdp


def _route(geo: dict, rid: str) -> dict:
    return next(f for f in geo["features"]
                if f["geometry"]["type"] != "Point"
                and f["properties"]["route_id"] == rid)


def _coords(feature: dict) -> list[list[float]]:
    g = feature["geometry"]
    if g["type"] == "LineString":
        return g["coordinates"]
    return [pt for line in g["coordinates"] for pt in line]


def test_rdp_returns_input_for_short_lines():
    pts = [[0.0, 0.0], [1.0, 1.0]]
    assert _rdp(pts, 0.1) == pts
    assert _rdp([], 0.1) == []


def test_rdp_zero_tolerance_is_noop():
    pts = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
    assert _rdp(pts, 0) == pts


def test_rdp_collinear_collapses_to_endpoints():
    pts = [[0.0, 0.0], [0.1, 0.0], [0.2, 0.0], [0.3, 0.0], [1.0, 0.0]]
    out = _rdp(pts, 0.0001)
    assert out == [[0.0, 0.0], [1.0, 0.0]]


def test_rdp_preserves_endpoints():
    pts = [[0.0, 0.0], [0.5, 0.5], [1.0, 0.0]]
    out = _rdp(pts, 100.0)  # tolerance way larger than any deviation
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]


def test_rdp_keeps_significant_bend():
    # Sharp peak at (0.5, 1.0) — should be kept under modest tolerance.
    pts = [[0.0, 0.0], [0.5, 1.0], [1.0, 0.0]]
    out = _rdp(pts, 0.01)
    assert out == pts


def test_simplify_reduces_point_count(demo_files, feed_factory):
    """Inject a long zig-zag shape and verify simplification drops most of it."""
    files = dict(demo_files)
    # Replace sh_b1 with 20 nearly-collinear vertices.
    rows = ["shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence"]
    for i in range(20):
        rows.append(f"sh_b1,37.97,{23.74 + i * 0.01:.6f},{i + 1}")
    rows.append("sh_t1,37.93,23.71,1")
    rows.append("sh_t1,37.925,23.725,2")
    files["shapes.txt"] = "\n".join(rows) + "\n"

    feed = feed_factory(files)
    full = convert(feed)
    simplified = convert(feed, simplify_tolerance=0.01)
    assert len(_coords(_route(full, "B1"))) > len(_coords(_route(simplified, "B1")))


def test_simplify_endpoints_match_original(demo_zip):
    full = convert(demo_zip)
    simplified = convert(demo_zip, simplify_tolerance=0.001)
    for rid in ("B1", "M1", "T1"):
        a = _coords(_route(full, rid))
        b = _coords(_route(simplified, rid))
        assert a[0] == b[0]
        assert a[-1] == b[-1]


def test_simplify_length_recomputed_post_simplify(demo_zip):
    """`length_km` on the feature must reflect the *simplified* geometry."""
    from gtfs2geojson.converter import _line_length_km
    g = convert(demo_zip, simplify_tolerance=0.0001)
    f = _route(g, "B1")
    coords = f["geometry"]["coordinates"] if f["geometry"]["type"] == "LineString" \
        else f["geometry"]["coordinates"][0]
    assert abs(f["properties"]["length_km"] - round(_line_length_km(coords), 3)) < 0.01
