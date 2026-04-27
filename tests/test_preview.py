"""Preview map rendering (v0.5): tiles, legend, sidebar, stop search."""
from __future__ import annotations

import pytest

folium = pytest.importorskip("folium")  # whole module needs the [preview] extra

from gtfs2geojson import convert
from gtfs2geojson.preview import (
    TILE_ALIASES,
    _legend_html,
    _sidebar_html,
    _summarise,
    render,
)


def _make_html(demo_zip, tmp_path, **kwargs) -> str:
    out = tmp_path / "preview.html"
    geo = convert(demo_zip)
    render(geo, out, **kwargs)
    return out.read_text(encoding="utf-8")


# ── unit-ish ────────────────────────────────────────────────────────────────

def test_tile_aliases_are_complete():
    assert set(TILE_ALIASES) == {"positron", "osm", "dark_matter"}


def test_summarise_counts_routes_stops_length(demo_zip):
    geo = convert(demo_zip)
    n_routes, by_mode, by_color, n_stops, length, agencies = _summarise(geo["features"])
    assert n_routes == 3
    assert by_mode == {"Bus": 1, "Metro": 1, "Tram": 1}
    assert n_stops == 6
    assert length > 20  # B1 is ~19 km, M1+T1 add a few more
    assert "DEMO" in agencies
    assert agencies["DEMO"] == "Demo Transit"


def test_summarise_handles_empty():
    n_routes, by_mode, _, n_stops, length, agencies = _summarise([])
    assert (n_routes, n_stops, length, agencies) == (0, 0, 0.0, {})
    assert by_mode == {}


def test_legend_html_contains_mode_color_and_count():
    html = _legend_html({"Bus": 5}, {"Bus": "#1976D2"})
    assert "#1976D2" in html
    assert "Bus (5)" in html
    assert 'id="g2g-legend"' in html


def test_sidebar_escapes_title():
    html = _sidebar_html("<script>alert(1)</script>", 0, {}, 0, 0.0, {})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_sidebar_collapses_long_agency_lists():
    agencies = {f"A{i}": f"Agency {i}" for i in range(10)}
    html = _sidebar_html("Big Feed", 0, {}, 0, 0.0, agencies)
    assert "Agencies: 10" in html
    assert "Agency 0" not in html  # full names not listed when > 3


# ── end-to-end render ──────────────────────────────────────────────────────

def test_default_render_emits_legend_sidebar_and_search(demo_zip, tmp_path):
    html = _make_html(demo_zip, tmp_path)
    assert 'id="g2g-legend"' in html
    assert 'id="g2g-sidebar"' in html
    # Search plugin loads as L.Control.Search.
    assert "Control.Search" in html or "L.Control.Search" in html
    # Default tiles = positron (CARTO).
    assert "cartodb-positron" in html or "cartodbpositron" in html.lower() \
        or "basemaps.cartocdn.com" in html


def test_render_with_dark_matter_tiles(demo_zip, tmp_path):
    html = _make_html(demo_zip, tmp_path, tiles="dark_matter")
    assert "dark" in html.lower()


def test_render_with_osm_tiles(demo_zip, tmp_path):
    html = _make_html(demo_zip, tmp_path, tiles="osm")
    assert "openstreetmap.org" in html.lower() or "tile.openstreetmap" in html.lower()


def test_render_passes_through_unknown_tile_string(demo_zip, tmp_path):
    """Strings that aren't aliases are forwarded straight to folium."""
    # Folium accepts CartoDB Voyager as a built-in name.
    html = _make_html(demo_zip, tmp_path, tiles="cartodbvoyager")
    assert "voyager" in html.lower() or "cartodb" in html.lower()


def test_render_includes_route_colors_in_layers(demo_zip, tmp_path):
    html = _make_html(demo_zip, tmp_path)
    # Bus default color appears in the per-route style function payload.
    assert "1976D2" in html.upper()
    # Metro red.
    assert "D32F2F" in html.upper()


def test_render_sidebar_shows_title_and_stats(demo_zip, tmp_path):
    html = _make_html(demo_zip, tmp_path, title="My Demo Feed")
    assert "My Demo Feed" in html
    assert "Routes: 3" in html
    assert "Stops: 6" in html
    assert "Length:" in html
    assert "Demo Transit" in html


def test_render_handles_feed_with_no_features(tmp_path):
    out = tmp_path / "empty.html"
    render({"type": "FeatureCollection", "features": []}, out, title="Empty")
    text = out.read_text(encoding="utf-8")
    # Sidebar still appears (so the user knows the file rendered);
    # legend is suppressed when there are no modes.
    assert 'id="g2g-sidebar"' in text
    assert 'id="g2g-legend"' not in text
    assert "Empty" in text
