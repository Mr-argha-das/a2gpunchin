from math import asin, cos, radians, sin, sqrt


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_meters = 6_371_000
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    a = sin(delta_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius_meters * asin(sqrt(a))


def within_geofence(employee_lat: float, employee_lon: float, office_lat: float, office_lon: float, radius_meters: float) -> tuple[bool, float]:
    distance = haversine_distance_meters(employee_lat, employee_lon, office_lat, office_lon)
    return distance <= radius_meters, round(distance, 2)
