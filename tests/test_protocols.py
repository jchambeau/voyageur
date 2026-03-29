"""Tests for TidalProvider and CartographyProvider Protocol compliance."""
import datetime

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import TidalState, Waypoint
from voyageur.tidal.protocol import TidalProvider


class MockTidalProvider:
    """Minimal mock implementing TidalProvider structurally."""

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        return TidalState(
            timestamp=at,
            current_direction=90.0,
            current_speed=1.5,
            water_height=3.0,
        )


class MockCartographyProvider:
    """Minimal mock implementing CartographyProvider structurally."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        return False


def test_tidal_provider_isinstance() -> None:
    assert isinstance(MockTidalProvider(), TidalProvider)


def test_cartography_provider_isinstance() -> None:
    assert isinstance(MockCartographyProvider(), CartographyProvider)


def test_tidal_provider_get_current(now: datetime.datetime) -> None:
    provider = MockTidalProvider()
    result = provider.get_current(lat=49.65, lon=-1.62, at=now)
    assert isinstance(result, TidalState)
    assert result.timestamp == now
    assert result.current_direction == 90.0
    assert result.current_speed == 1.5
    assert result.water_height == 3.0


def test_cartography_provider_intersects_land(now: datetime.datetime) -> None:
    provider = MockCartographyProvider()
    wp = Waypoint(
        lat=49.65, lon=-1.62, timestamp=now, heading=180.0, speed_over_ground=5.0
    )
    result = provider.intersects_land(route=[wp])
    assert result is False
