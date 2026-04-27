"""Generate a Folium preview map from a GTFS-derived GeoJSON FeatureCollection."""
from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path

# Friendly aliases for `tiles=` so users don't have to memorise folium's strings.
TILE_ALIASES: dict[str, str] = {
    "positron": "cartodbpositron",
    "osm": "openstreetmap",
    "dark_matter": "cartodbdark_matter",
}


def _bounds(features: list[dict]) -> tuple[float, float, float, float]:
    lons, lats = [], []
    for f in features:
        g = f["geometry"]
        if g["type"] == "Point":
            lons.append(g["coordinates"][0])
            lats.append(g["coordinates"][1])
        elif g["type"] == "LineString":
            for x, y in g["coordinates"]:
                lons.append(x); lats.append(y)
        elif g["type"] == "MultiLineString":
            for line in g["coordinates"]:
                for x, y in line:
                    lons.append(x); lats.append(y)
    if not lons:
        return (-10, 35, 30, 60)  # rough Europe fallback
    return (min(lons), min(lats), max(lons), max(lats))


def _summarise(features: list[dict]):
    """Tally what's in the FeatureCollection for the legend + sidebar."""
    by_mode_count: dict[str, int] = defaultdict(int)
    by_mode_color: dict[str, str] = {}
    n_stops = 0
    total_length_km = 0.0
    agencies: dict[str, str] = {}
    for f in features:
        p = f.get("properties", {})
        if f["geometry"]["type"] == "Point":
            n_stops += 1
            continue
        mode = p.get("mode", "Other")
        by_mode_count[mode] += 1
        by_mode_color.setdefault(mode, p.get("route_color", "#888"))
        total_length_km += float(p.get("length_km", 0) or 0)
        aid = p.get("agency_id", "")
        if aid and aid not in agencies:
            agencies[aid] = p.get("agency_name", "") or aid
    n_routes = sum(by_mode_count.values())
    return n_routes, dict(by_mode_count), by_mode_color, n_stops, total_length_km, agencies


def _legend_html(by_mode_count: dict[str, int], by_mode_color: dict[str, str]) -> str:
    rows = []
    for mode in sorted(by_mode_count):
        rows.append(
            f'<div style="display:flex;align-items:center;margin:2px 0;">'
            f'<span style="display:inline-block;width:14px;height:4px;'
            f'background:{by_mode_color[mode]};margin-right:6px;flex-shrink:0;"></span>'
            f'{html.escape(mode)} ({by_mode_count[mode]})'
            f'</div>'
        )
    return (
        '<div id="g2g-legend" style="position:absolute;bottom:30px;right:10px;'
        'background:rgba(255,255,255,.95);padding:8px 12px;border-radius:6px;'
        'border:1px solid #ddd;font:12px/1.4 system-ui,-apple-system,sans-serif;'
        'z-index:1000;box-shadow:0 2px 6px rgba(0,0,0,.15);">'
        '<div style="font-weight:bold;margin-bottom:6px;">Modes</div>'
        + "".join(rows) +
        '</div>'
    )


def _sidebar_html(
    title: str,
    n_routes: int,
    by_mode_count: dict[str, int],
    n_stops: int,
    total_length_km: float,
    agencies: dict[str, str],
) -> str:
    parts: list[str] = []
    if agencies:
        names = sorted(agencies.values())
        if len(names) <= 3:
            parts.append(f'<div>Agencies: {html.escape(", ".join(names))}</div>')
        else:
            parts.append(f"<div>Agencies: {len(names)}</div>")
    if by_mode_count:
        modes_str = " · ".join(f"{html.escape(m)} {n}" for m, n in sorted(by_mode_count.items()))
        parts.append(f"<div>Routes: {n_routes} ({modes_str})</div>")
    parts.append(f"<div>Stops: {n_stops}</div>")
    if total_length_km > 0:
        parts.append(f"<div>Length: {total_length_km:.1f} km</div>")
    body = "".join(parts) or "<div>No features</div>"
    return (
        '<details id="g2g-sidebar" open style="position:absolute;bottom:30px;left:10px;'
        'background:rgba(255,255,255,.95);padding:8px 12px;border-radius:6px;'
        'border:1px solid #ddd;font:12px/1.4 system-ui,-apple-system,sans-serif;'
        'max-width:280px;z-index:1000;box-shadow:0 2px 6px rgba(0,0,0,.15);">'
        f'<summary style="font-weight:bold;cursor:pointer;outline:none;">'
        f'{html.escape(title)}</summary>'
        f'<div style="margin-top:6px;">{body}</div>'
        '</details>'
    )


def render(
    geojson: dict,
    out_path: str | Path,
    *,
    title: str = "GTFS preview",
    tiles: str = "positron",
) -> None:
    """Write an interactive Folium HTML preview of the GeoJSON.

    Routes are rendered per-mode as toggleable layers using each feature's
    ``route_color`` property. Stops are rendered as a searchable circle layer
    (``folium.plugins.Search`` keyed on ``stop_name``).

    A legend (top-right) lists the modes with their colours and counts.
    A collapsible sidebar (bottom-left) shows the title, agencies, route
    counts by mode, stop count, and total network length.

    Parameters
    ----------
    geojson : the FeatureCollection produced by ``convert()``.
    out_path : where to write the HTML map.
    title : shown in the sidebar header.
    tiles : either an alias (``"positron"`` / ``"osm"`` / ``"dark_matter"``)
        or any string Folium accepts as its ``tiles`` argument (built-in name
        or a tile-URL template).
    """
    try:
        import folium
        from folium.plugins import Search
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "folium is required for preview rendering. Install with: pip install folium"
        ) from e

    feats = geojson.get("features", [])
    w, s, e, n = _bounds(feats)
    cx, cy = (w + e) / 2, (s + n) / 2

    tile_arg = TILE_ALIASES.get(tiles, tiles)
    m = folium.Map(location=[cy, cx], zoom_start=11, tiles=tile_arg)
    m.fit_bounds([[s, w], [n, e]])

    # Bucket routes by mode (one toggleable layer per mode); collect stops separately.
    by_mode: dict[str, list[dict]] = defaultdict(list)
    stop_feats: list[dict] = []
    for f in feats:
        if f["geometry"]["type"] == "Point":
            stop_feats.append(f)
        else:
            mode = f["properties"].get("mode", "Other")
            by_mode[mode].append(f)

    for mode, mode_feats in sorted(by_mode.items()):
        layer = folium.FeatureGroup(name=f"{mode} ({len(mode_feats)})", show=True)
        for f in mode_feats:
            color = f["properties"].get("route_color", "#1976D2")
            short = f["properties"].get("route_short_name", "")
            long_ = f["properties"].get("route_long_name", "")
            tip = f"<b>{html.escape(short)}</b> {html.escape(long_)}" \
                if short or long_ else html.escape(mode)
            folium.GeoJson(
                f,
                style_function=lambda _f, c=color: {"color": c, "weight": 3, "opacity": 0.85},
                tooltip=folium.Tooltip(tip, sticky=True),
            ).add_to(layer)
        layer.add_to(m)

    if stop_feats:
        # GeoJson layer (rather than MarkerCluster) so folium.plugins.Search
        # can index the features by stop_name. Each stop becomes a small dot.
        stops_layer = folium.GeoJson(
            {"type": "FeatureCollection", "features": stop_feats},
            name=f"Stops ({len(stop_feats)})",
            show=False,
            marker=folium.CircleMarker(
                radius=3, color="#444", weight=1, fill=True,
                fill_color="#fff", fill_opacity=0.9,
            ),
            tooltip=folium.GeoJsonTooltip(fields=["stop_name"], aliases=[""]),
        )
        stops_layer.add_to(m)
        Search(
            layer=stops_layer,
            search_label="stop_name",
            placeholder="Search stops…",
            collapsed=False,
            position="topleft",
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    n_routes, by_mode_count, by_mode_color, n_stops, total_length, agencies = _summarise(feats)
    if by_mode_count:
        m.get_root().html.add_child(
            folium.Element(_legend_html(by_mode_count, by_mode_color))
        )
    m.get_root().html.add_child(folium.Element(
        _sidebar_html(title, n_routes, by_mode_count, n_stops, total_length, agencies)
    ))

    m.save(str(out_path))
