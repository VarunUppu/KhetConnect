# File: backend/app/services/geo_service.py
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape


def make_point(lat: float, lng: float) -> WKTElement:
    """Build a geography point. WKT order is POINT(lng lat)."""
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def lat_lng(location) -> tuple[float | None, float | None]:
    """Extract (lat, lng) from a geography value; (None, None) if unset."""
    if location is None:
        return None, None
    point = to_shape(location)
    return point.y, point.x