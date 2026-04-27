"""Generate a Folium preview map from a GTFS-derived GeoJSON FeatureCollection."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path


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


def render(geojson: dict, out_path: str | Path, *, title: str = "GTFS preview") -> None:
    """Write an interactive Folium HTML preview of the GeoJSON.

    Stops are rendered as a clusterable circle layer; routes are rendered per-mode
    as toggleable layers using each feature's `route_color` property.
    """
    try:
        import folium
        from folium.plugins import MarkerCluster
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "folium is required for preview rendering. Install with: pip install folium"
        ) from e

    feats = geojson.get("features", [])
    w, s, e, n = _bounds(feats)
    cx, cy = (w + e) / 2, (s + n) / 2

    m = folium.Map(location=[cy, cx], zoom_start=11, tiles="cartodbpositron",
                   attr="© OpenStreetMap contributors © CARTO")
    m.fit_bounds([[s, w], [n, e]])

    # Group route features by mode for layer toggling
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
            tip = f"<b>{short}</b> {long_}" if short or long_ else mode
            folium.GeoJson(
                f,
                style_function=lambda _f, c=color: {"color": c, "weight": 3, "opacity": 0.85},
                tooltip=folium.Tooltip(tip, sticky=True),
            ).add_to(layer)
        layer.add_to(m)

    if stop_feats:
        stops_layer = folium.FeatureGroup(name=f"Stops ({len(stop_feats)})", show=False)
        cluster = MarkerCluster(disable_clustering_at_zoom=15).add_to(stops_layer)
        for f in stop_feats:
            x, y = f["geometry"]["coordinates"]
            name = f["properties"].get("stop_name", "")
            folium.CircleMarker(
                location=[y, x], radius=3, color="#444", weight=1,
                fill=True, fill_color="#fff", fill_opacity=0.9,
                tooltip=name,
            ).add_to(cluster)
        stops_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    folium.map.Marker(
        [n, e], icon=folium.DivIcon(html=(
            f'<div style="background:rgba(255,255,255,.9);padding:4px 8px;'
            f'border-radius:4px;font:12px/1.4 system-ui;border:1px solid #ddd">{title}</div>'
        )),
    ).add_to(m)

    m.save(str(out_path))
