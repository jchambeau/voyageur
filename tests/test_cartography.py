"""Tests for GeoJsonCartography — Story 3.1."""
import datetime

from voyageur.cartography.impl import GeoJsonCartography
from voyageur.models import Waypoint

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)


def _wp(lat: float, lon: float) -> Waypoint:
    return Waypoint(lat=lat, lon=lon, timestamp=NOW, heading=0.0, speed_over_ground=0.0)


def test_intersects_land_for_crossing_route() -> None:
    """Route traversant la péninsule Cotentin (~49.5°N d'ouest en est) → True."""
    route = [_wp(49.5, -2.2), _wp(49.5, -1.2)]
    assert GeoJsonCartography().intersects_land(route) is True


def test_no_intersection_for_offshore_route() -> None:
    """Route en Manche au nord (50.5°N), loin des terres → False."""
    route = [_wp(50.5, -2.0), _wp(50.5, 0.0)]
    assert GeoJsonCartography().intersects_land(route) is False
