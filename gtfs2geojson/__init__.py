"""gtfs2geojson — convert GTFS feeds to GeoJSON with optional Folium preview."""
from .converter import (
    ROUTE_TYPE_MAP,
    convert,
    list_agencies,
    list_modes,
    write,
)

__version__ = "0.4.0"
__all__ = [
    "convert",
    "write",
    "list_modes",
    "list_agencies",
    "ROUTE_TYPE_MAP",
]
