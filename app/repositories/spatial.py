from typing import Any

from geoalchemy2 import Geography, WKTElement
from sqlalchemy import cast, func

WGS84_SRID = 4326


def point_from_coordinates(latitude: float, longitude: float) -> Any:
    return func.ST_SetSRID(func.ST_Point(longitude, latitude), WGS84_SRID)


def line_from_coordinates(points: list[tuple[float, float]]) -> Any:
    vertices = ", ".join(f"{longitude} {latitude}" for latitude, longitude in points)
    return WKTElement(f"LINESTRING({vertices})", srid=WGS84_SRID)


def as_geography(geometry: Any) -> Any:
    return cast(geometry, Geography)
