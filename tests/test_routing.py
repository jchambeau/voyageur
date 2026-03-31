"""Tests for RoutePlanner (2.2), IsochroneRoutePlanner (4.1), MultiCriteria (4.2),
OptimalDeparturePlanner (4.3)."""
import datetime
import time

import pytest

from voyageur.models import (
    BoatProfile,
    Route,
    SafetyThresholds,
    TidalState,
    WindCondition,
)
from voyageur.routing.departure import DepartureResult, OptimalDeparturePlanner
from voyageur.routing.isochrone import IsochroneRoutePlanner
from voyageur.routing.multi import CRITERIA, MultiCriteriaRoutePlanner
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


def test_isochrone_performance_nfr2_1min_step(mock_tidal, mock_cartography, boat, now):
    """Cherbourg→Granville at 1-min step must complete in under 30 s (NFR2)."""
    planner = IsochroneRoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    t0 = time.perf_counter()
    route = planner.compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=1,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0, f"NFR2 violated: {elapsed:.3f}s (limit: 30s)"
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
    assert all(wp.flagged for wp in route.waypoints)


def test_safety_partial_current_flags(mock_cartography, boat, now):
    """Courant élevé sur 1er waypoint seulement → flag partiel (AC6)."""
    from voyageur.models import TidalState

    call_count = 0

    class _FirstStepHighCurrentTidal:
        def get_current(
            self, lat: float, lon: float, at: datetime.datetime
        ) -> TidalState:
            nonlocal call_count
            call_count += 1
            speed = 3.0 if call_count == 1 else 0.5
            return TidalState(
                timestamp=at,
                current_direction=90.0,
                current_speed=speed,
                water_height=0.0,
            )

    planner = RoutePlanner(
        tidal=_FirstStepHighCurrentTidal(), cartography=mock_cartography
    )
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_current_kn=2.0)
    count = evaluate_route(route, wind, thresholds)
    assert 0 < count < len(route.waypoints), (
        f"Expected partial flags, got {count}/{len(route.waypoints)}"
    )
    assert route.waypoints[0].flagged
    assert not route.waypoints[-1].flagged


# ---------------------------------------------------------------------------
# IsochroneRoutePlanner — Story 4.1
# ---------------------------------------------------------------------------


def test_isochrone_clear_route_unchanged(mock_tidal, mock_cartography, boat, now):
    """Sans obstacle : IsochroneRoutePlanner = RoutePlanner."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    direct = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography).compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    iso = IsochroneRoutePlanner(
        tidal=mock_tidal, cartography=mock_cartography
    ).compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(iso.waypoints) == len(direct.waypoints)
    assert iso.waypoints[0].lat == pytest.approx(direct.waypoints[0].lat)
    assert iso.waypoints[0].lon == pytest.approx(direct.waypoints[0].lon)
    assert iso.waypoints[-1].lat == pytest.approx(direct.waypoints[-1].lat, abs=0.01)
    assert iso.waypoints[-1].lon == pytest.approx(direct.waypoints[-1].lon, abs=0.01)


def test_isochrone_avoids_obstacle(mock_tidal, boat, now):
    """Bearing direct bloqué → beam search dévie vers le premier heading libre."""
    # Bloquer le premier appel (offset=0, bearing direct pour étape 1)
    # → le beam search passe à offset=+15° et prend ce heading
    responses = iter([True, False])  # premier appel bloqué, tous les suivants libres

    class _BlockFirstSegment:
        def intersects_land(self, route):
            return next(responses, False)

    carto = _BlockFirstSegment()
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = IsochroneRoutePlanner(tidal=mock_tidal, cartography=carto).compute(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(route.waypoints) >= 2
    assert route.total_duration > datetime.timedelta(0)
    # heading[0] doit être dévié de +15° du bearing direct (premier offset libre)
    # bearing Cherbourg→Granville ≈ 178° → heading dévié ≈ 193°
    assert abs(route.waypoints[0].heading - 178.0) > 5.0


# ---------------------------------------------------------------------------
# MultiCriteriaRoutePlanner — Story 4.2
# ---------------------------------------------------------------------------


def test_multi_criteria_fastest_and_comfort_are_distinct(
    mock_tidal, mock_cartography, boat, now
):
    """Fastest et comfort doivent sélectionner des headings différents."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = MultiCriteriaRoutePlanner(
        tidal=mock_tidal, cartography=mock_cartography
    )
    results = planner.compute_all(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
        criteria=["fastest", "comfort"],
    )
    assert "fastest" in results
    assert "comfort" in results
    fastest = results["fastest"]
    comfort = results["comfort"]
    assert isinstance(fastest, Route)
    assert isinstance(comfort, Route)
    # Bearing Cherbourg→Granville ≈ 178°, vent 240° → TWA direct ≈ 62°
    # fastest : heading ≈ 178° ; comfort : heading ≈ 150° (TWA ≈ 90°)
    assert fastest.waypoints[0].heading != comfort.waypoints[0].heading


def test_multi_criteria_all_returns_four_routes(
    mock_tidal, mock_cartography, boat, now
):
    """compute_all avec tous les critères retourne 4 routes valides."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = MultiCriteriaRoutePlanner(
        tidal=mock_tidal, cartography=mock_cartography
    )
    results = planner.compute_all(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(results) == len(CRITERIA)
    for label, route in results.items():
        assert isinstance(route, Route), f"{label}: expected Route"
        assert len(route.waypoints) >= 1, f"{label}: no waypoints"


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


# ---------------------------------------------------------------------------
# OptimalDeparturePlanner — Story 4.3
# ---------------------------------------------------------------------------


class _EarlyFavorableTidalProvider:
    """Returns 3kn southbound current before 07:00 UTC, zero otherwise."""

    def get_current(self, lat: float, lon: float, at: datetime.datetime) -> TidalState:
        if at.hour < 7:
            return TidalState(
                timestamp=at,
                current_direction=180.0,
                current_speed=3.0,
                water_height=0.0,
            )
        return TidalState(
            timestamp=at,
            current_direction=0.0,
            current_speed=0.0,
            water_height=0.0,
        )


def test_optimal_departure_6h_window_returns_earlier_departure(mock_cartography, boat):
    """Optimal departure avec courant favorable avant 07:00 doit être avant 08:00."""
    UTC = datetime.timezone.utc
    window_start = datetime.datetime(2026, 3, 29, 6, 0, tzinfo=UTC)
    window_end = datetime.datetime(2026, 3, 29, 12, 0, tzinfo=UTC)
    baseline = datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)
    wind = WindCondition(timestamp=window_start, direction=240.0, speed=15.0)
    planner = OptimalDeparturePlanner(
        tidal=_EarlyFavorableTidalProvider(), cartography=mock_cartography
    )
    result = planner.scan(
        origin=CHERBOURG,
        destination=GRANVILLE,
        window_start=window_start,
        window_end=window_end,
        baseline_departure=baseline,
        wind=wind,
        boat=boat,
        scan_interval_minutes=30,
    )
    assert result.optimal_departure.hour < 8
    assert result.time_saved.total_seconds() > 0


def test_optimal_departure_result_contains_route(mock_cartography, boat):
    """DepartureResult contient une Route valide avec au moins 1 waypoint."""
    UTC = datetime.timezone.utc
    window_start = datetime.datetime(2026, 3, 29, 6, 0, tzinfo=UTC)
    window_end = datetime.datetime(2026, 3, 29, 12, 0, tzinfo=UTC)
    baseline = datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)
    wind = WindCondition(timestamp=window_start, direction=240.0, speed=15.0)
    planner = OptimalDeparturePlanner(
        tidal=_EarlyFavorableTidalProvider(), cartography=mock_cartography
    )
    result = planner.scan(
        origin=CHERBOURG,
        destination=GRANVILLE,
        window_start=window_start,
        window_end=window_end,
        baseline_departure=baseline,
        wind=wind,
        boat=boat,
        scan_interval_minutes=30,
    )
    assert isinstance(result, DepartureResult)
    assert isinstance(result.optimal_route, Route)
    assert len(result.optimal_route.waypoints) >= 1
