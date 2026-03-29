"""Shared fixtures for all test modules."""
import datetime

import pytest

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import TidalState, Waypoint
from voyageur.tidal.protocol import TidalProvider

UTC = datetime.timezone.utc


@pytest.fixture
def now() -> datetime.datetime:
    """A fixed UTC datetime for use in tests."""
    return datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)


class _ZeroTidalProvider:
    """Mock TidalProvider returning zero-current TidalState for routing tests."""

    def get_current(self, lat: float, lon: float, at: datetime.datetime) -> TidalState:
        """Return a zero-current TidalState."""
        return TidalState(
            timestamp=at, current_direction=0.0, current_speed=0.0, water_height=0.0
        )


class _NoObstacleCartographyProvider:
    """Mock CartographyProvider returning False for all routes."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        """Return False — no obstacles."""
        return False


@pytest.fixture
def mock_tidal() -> TidalProvider:
    """Zero-current TidalProvider for routing tests."""
    return _ZeroTidalProvider()


@pytest.fixture
def mock_cartography() -> CartographyProvider:
    """No-obstacle CartographyProvider for routing tests."""
    return _NoObstacleCartographyProvider()
