from math import cos, radians

from shapely.geometry import LineString

METERS_PER_DEGREE = 111_320.0
SIMPLIFY_TOLERANCE_DEGREES = 0.00005

LatLng = tuple[float, float]


def coverage_ring(points: list[LatLng], radius_m: int) -> list[LatLng]:
    scale = cos(radians(sum(lat for lat, _ in points) / len(points)))
    line = LineString([(lng * scale, lat) for lat, lng in points])
    corridor = line.buffer(radius_m / METERS_PER_DEGREE).simplify(SIMPLIFY_TOLERANCE_DEGREES)
    return [(lat, lng / scale) for lng, lat in corridor.exterior.coords]
