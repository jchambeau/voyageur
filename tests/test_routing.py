"""Tests for RoutePlanner — Story 2.2."""
import datetime
import time

import pytest

from voyageur.models import BoatProfile, Route, SafetyThresholds, WindCondition
from voyageur.routing.planner import MAX_STEPS, RoutePlanner
from voyageur.routing.safety import evaluate_route

# Reference port coordinates (lat, lon)
CHERBOURG = (49.6453, -1.6222)
GRANVILLE = (48.8327, -1.5971)   # ~55 NM south of Cherbourg
LE_HAVRE = (49.4892, 0.1080)     # ~85 NM east of Cherbourg (NFR1 test)

UTC = datetime.timezone.utc


@pytest.fixture
def boat() -> BoatProfile:
    """Standard test boat profile."""
    return BoatProfile(
        name="Test Boat", loa=12.0, draft=1.8, sail_area=65.0, default_step=15
    )


@pytest.fixture
def westerly_wind(now: datetime.datetime) -> WindCondition:
    """15-knot wind from the SW (240°) — favourable for southbound passages."""
    return WindCondition(timestamp=now, direction=240.0, speed=15.0)


# ---------------------------------------------------------------------------
# Happy path: Cherbourg → Granville
# ---------------------------------------------------------------------------


def test_compute_returns_route(mock_tidal, mock_cartography, boat, westerly_wind, now):
    """compute() must return a Route instance."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    assert isinstance(route, Route)


def test_compute_route_has_waypoints(
    mock_tidal, mock_cartography, boat, westerly_wind, now
):
    """Route must contain at least one waypoint."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    assert len(route.waypoints) >= 1


def test_waypoint_fields_valid(mock_tidal, mock_cartography, boat, westerly_wind, now):
    """Every waypoint must have valid lat, lon, heading [0, 360), SOG ≥ 0."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    for i, wp in enumerate(route.waypoints):
        assert -90.0 <= wp.lat <= 90.0, f"Waypoint {i}: lat out of range"
        assert -180.0 <= wp.lon <= 180.0, f"Waypoint {i}: lon out of range"
        assert 0.0 <= wp.heading < 360.0, f"Waypoint {i}: heading not in [0, 360)"
        assert wp.speed_over_ground >= 0.0, f"Waypoint {i}: SOG < 0"


def test_waypoint_timestamps_increment(
    mock_tidal, mock_cartography, boat, westerly_wind, now
):
    """Each waypoint timestamp must increase by exactly step_minutes."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    step_minutes = 15
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
        step_minutes=step_minutes,
    )
    step = datetime.timedelta(minutes=step_minutes)
    for i, wp in enumerate(route.waypoints[:-1]):
        expected = now + i * step
        assert wp.timestamp == expected, (
            f"Waypoint {i}: expected {expected}, got {wp.timestamp}"
        )


def test_route_departure_time(mock_tidal, mock_cartography, boat, westerly_wind, now):
    """Route.departure_time must match the provided departure_time."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    assert route.departure_time == now


def test_total_duration_positive(
    mock_tidal, mock_cartography, boat, westerly_wind, now
):
    """Route.total_duration must be a non-negative timedelta."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    assert route.total_duration >= datetime.timedelta(0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_origin_equals_destination(
    mock_tidal, mock_cartography, boat, westerly_wind, now
):
    """When origin == destination, route must return immediately with one waypoint."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=CHERBOURG,
        destination=CHERBOURG,
        departure_time=now,
        wind=westerly_wind,
        boat=boat,
    )
    assert isinstance(route, Route)
    assert len(route.waypoints) == 1
    assert route.total_duration == datetime.timedelta(0)


def test_zero_wind_zero_current_does_not_raise(
    mock_tidal, mock_cartography, boat, now
):
    """Zero wind + zero tidal current must not raise; returns partial route."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    zero_wind = WindCondition(timestamp=now, direction=0.0, speed=0.0)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=zero_wind,
        boat=boat,
    )
    assert isinstance(route, Route)
    assert len(route.waypoints) <= MAX_STEPS


def test_step_minutes_1(mock_tidal, mock_cartography, boat, now):
    """step_minutes=1 must work without error and produce valid waypoints."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=1,
    )
    assert isinstance(route, Route)
    assert len(route.waypoints) >= 1


# ---------------------------------------------------------------------------
# Performance — NFR1
# ---------------------------------------------------------------------------


def test_performance_nfr1_15min_step(mock_tidal, mock_cartography, boat, now):
    """Cherbourg→Le Havre (~85 NM) at 15-min step must complete in under 5 s (NFR1)."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=270.0, speed=15.0)
    t0 = time.perf_counter()
    route = planner.compute(
        origin=CHERBOURG,
        destination=LE_HAVRE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"NFR1 violated: {elapsed:.3f}s (limit: 5s)"
    assert len(route.waypoints) > 0


# ---------------------------------------------------------------------------
# Tidal current integration
# ---------------------------------------------------------------------------


def test_nonzero_tidal_current_affects_sog(mock_tidal, mock_cartography, boat, now):
    """Non-zero tidal current must change SOG compared to zero-current baseline."""
    from voyageur.models import TidalState

    class _EastwardTidalProvider:
        """Mock returning a constant 2-knot eastward current."""

        def get_current(
            self, lat: float, lon: float, at: datetime.datetime
        ) -> TidalState:
            """Return a fixed eastward TidalState."""
            return TidalState(
                timestamp=at,
                current_direction=90.0,
                current_speed=2.0,
                water_height=0.0,
            )

    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner_no_tide = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    planner_with_tide = RoutePlanner(
        tidal=_EastwardTidalProvider(), cartography=mock_cartography
    )

    route_no_tide = planner_no_tide.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    route_with_tide = planner_with_tide.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )

    sog_no_tide = route_no_tide.waypoints[0].speed_over_ground
    sog_with_tide = route_with_tide.waypoints[0].speed_over_ground
    assert sog_no_tide != sog_with_tide, (
        f"Tidal had no effect on SOG: both = {sog_no_tide:.3f} kn"
    )


# ---------------------------------------------------------------------------
# Safety threshold evaluation — Story 3.2
# ---------------------------------------------------------------------------


def test_safety_flags_exceed_wind(mock_tidal, mock_cartography, boat, now):
    """Wind=15 kn > max_wind=10 kn → tous waypoints flagués."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_wind_kn=10.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == len(route.waypoints)
    assert all(wp.flagged for wp in route.waypoints)


def test_safety_no_flags_within_thresholds(mock_tidal, mock_cartography, boat, now):
    """Wind=15 kn < max_wind=20 kn → aucun waypoint flagué."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_wind_kn=20.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == 0
    assert not any(wp.flagged for wp in route.waypoints)


def test_safety_flags_exceed_current(mock_cartography, boat, now):
    """Courant=3 kn > max_current=2 kn → tous waypoints flagués."""
    from voyageur.models import TidalState

    class _HighCurrentTidal:
        def get_current(
            self, lat: float, lon: float, at: datetime.datetime
        ) -> TidalState:
            return TidalState(
                timestamp=at,
                current_direction=90.0,
                current_speed=3.0,
                water_height=0.0,
            )

    planner = RoutePlanner(tidal=_HighCurrentTidal(), cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_current_kn=2.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == len(route.waypoints)


def test_safety_no_thresholds_no_flags(mock_tidal, mock_cartography, boat, now):
    """Sans seuils définis → aucun waypoint flagué."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds()
    count = evaluate_route(route, wind, thresholds)
    assert count == 0
