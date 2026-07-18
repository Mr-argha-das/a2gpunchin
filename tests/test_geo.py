from app.utils.geo import haversine_distance_meters, within_geofence


def test_haversine_distance_for_same_point_is_zero():
    assert haversine_distance_meters(19.076, 72.8777, 19.076, 72.8777) == 0


def test_geofence_accepts_location_inside_radius():
    accepted, distance = within_geofence(19.076, 72.8777, 19.0761, 72.8778, 100)
    assert accepted is True
    assert distance < 100
