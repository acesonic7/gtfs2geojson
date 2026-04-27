"""gtfs2geojson — convert GTFS feeds to GeoJSON with optional Folium preview."""
from .converter import convert, write, ROUTE_TYPE_MAP

__version__ = "0.2.0"
__all__ = ["convert", "write", "ROUTE_TYPE_MAP"]
