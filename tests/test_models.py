"""Tests for voyageur.models dataclasses."""
import datetime

from voyageur.models import BoatProfile, Route, TidalState, Waypoint, WindCondition


def test_boat_profile() -> None:
    profile = BoatProfile(
        name="Zephyr", loa=9.5, draft=1.2, sail_area=42.0, default_step=15
    )
    assert profile.name == "Zephyr"
    assert profile.loa == 9.5
    assert profile.draft == 1.2
    assert profile.sail_area == 42.0
    assert profile.default_step == 15


def test_waypoint(now: datetime.datetime) -> None:
    wp = Waypoint(
        lat=49.65, lon=-1.62, timestamp=now, heading=180.0, speed_over_ground=5.0
    )
    assert wp.lat == 49.65
    assert wp.lon == -1.62
    assert wp.timestamp.tzinfo is not None
    assert wp.heading == 180.0
    assert wp.speed_over_ground == 5.0


def test_tidal_state(now: datetime.datetime) -> None:
    ts = TidalState(
        timestamp=now, current_direction=90.0, current_speed=2.5, water_height=4.8
    )
    assert ts.timestamp.tzinfo is not None
    assert ts.current_direction == 90.0
    assert ts.current_speed == 2.5
    assert ts.water_height == 4.8


def test_wind_condition(now: datetime.datetime) -> None:
    wc = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    assert wc.timestamp.tzinfo is not None
    assert wc.direction == 240.0
    assert wc.speed == 15.0


def test_route_defaults(now: datetime.datetime) -> None:
    route = Route(departure_time=now)
    assert route.departure_time.tzinfo is not None
    assert route.waypoints == []
    assert route.total_duration == datetime.timedelta(0)


def test_route_with_waypoints(now: datetime.datetime) -> None:
    wp = Waypoint(
        lat=49.65, lon=-1.62, timestamp=now, heading=180.0, speed_over_ground=5.0
    )
    route = Route(
        departure_time=now,
        waypoints=[wp],
        total_duration=datetime.timedelta(hours=2),
    )
    assert len(route.waypoints) == 1
    assert route.total_duration == datetime.timedelta(hours=2)
