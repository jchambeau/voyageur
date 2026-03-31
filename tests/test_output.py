"""Tests for format_timeline and format_multi_criteria — Story 2.3."""
import datetime

import pytest

from voyageur.models import Route, WindCondition
from voyageur.output.formatter import format_multi_criteria, format_timeline

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_route(mock_tidal, mock_cartography, now) -> Route:
    """Route Cherbourg→Granville with at least 20 waypoints."""
    from voyageur.models import BoatProfile
    from voyageur.routing.planner import RoutePlanner

    boat = BoatProfile(
        name="Test", loa=12.0, draft=1.8, sail_area=65.0, default_step=15
    )
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=(49.6453, -1.6222),
        destination=(48.8327, -1.5971),
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(route.waypoints) >= 20, "Fixture must produce ≥20 waypoints"
    return route


# ---------------------------------------------------------------------------
# 80-column constraint (AC3)
# ---------------------------------------------------------------------------


def test_80_col_constraint(sample_route, now):
    """Every line of the formatted output must be ≤ 80 chars."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    output = format_timeline(sample_route, wind=wind)
    for i, line in enumerate(output.splitlines()):
        assert len(line) <= 80, f"Line {i} exceeds 80 cols ({len(line)}): {line!r}"


# ---------------------------------------------------------------------------
# Headers present (AC1/2)
# ---------------------------------------------------------------------------


def test_headers_present(sample_route, now):
    """Output must contain header labels TIME, LAT, LON, HDG, SOG."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    output = format_timeline(sample_route, wind=wind)
    for label in ("TIME", "LAT", "LON", "HDG", "SOG"):
        assert label in output, f"Header '{label}' missing from output"


# ---------------------------------------------------------------------------
# Summary section (AC4)
# ---------------------------------------------------------------------------


def test_summary_present(sample_route, now):
    """Output must contain 'NM' and 'Duration' in summary section."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    output = format_timeline(sample_route, wind=wind)
    assert "NM" in output, "'NM' missing from summary"
    assert "Duration" in output, "'Duration' missing from summary"


# ---------------------------------------------------------------------------
# Empty route edge case (AC5)
# ---------------------------------------------------------------------------


def test_empty_route_does_not_raise(now):
    """format_timeline with 0 waypoints must return a string without raising."""
    empty_route = Route(departure_time=now)
    result = format_timeline(empty_route)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Wind=None produces placeholder
# ---------------------------------------------------------------------------


def test_wind_none_placeholder(sample_route):
    """When wind=None, wind column must show 8-char placeholder '---/----'."""
    output = format_timeline(sample_route, wind=None)
    assert "---/----" in output


# ---------------------------------------------------------------------------
# format_multi_criteria
# ---------------------------------------------------------------------------


def test_format_multi_criteria_sections(sample_route, now):
    """format_multi_criteria must produce one labelled section per criterion."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    results = {"fastest": sample_route, "comfort": sample_route}
    output = format_multi_criteria(results, wind=wind)
    assert "=== FASTEST ===" in output
    assert "=== COMFORT ===" in output
    assert output.count("Total:") == 2


def test_format_multi_criteria_wind_source(sample_route, now):
    """format_multi_criteria must forward wind_source to each section footer."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    results = {"fastest": sample_route}
    output = format_multi_criteria(results, wind=wind, wind_source="OpenMeteo")
    assert "forecast (OpenMeteo)" in output


def test_format_timeline_wind_source(sample_route, now):
    """format_timeline must append wind_source to summary when provided."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    output = format_timeline(sample_route, wind=wind, wind_source="OpenMeteo")
    assert "forecast (OpenMeteo)" in output
