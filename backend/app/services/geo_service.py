# File: backend/app/services/geo_service.py
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import func


def make_point(lat: float, lng: float) -> WKTElement:
    """Build a geography point. WKT order is POINT(lng lat)."""
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def lat_lng(location) -> tuple[float | None, float | None]:
    """Extract (lat, lng) from a geography value; (None, None) if unset."""
    if location is None:
        return None, None
    point = to_shape(location)
    return point.y, point.x


def geog_point(lat: float, lng: float):
    """SQL *expression* for a geography point, for use inside queries (WHERE / ORDER BY).

    make_point() builds a value to STORE; this builds an expression to COMPARE against.
    The WKT string is passed to PostGIS as a bound parameter (never concatenated into SQL).
    Format `.10f` avoids scientific notation; 1e-10 degrees is far below GPS precision.
    Remember: WKT order is POINT(lng lat).
    """
    return func.ST_GeogFromText(f"SRID=4326;POINT({lng:.10f} {lat:.10f})")