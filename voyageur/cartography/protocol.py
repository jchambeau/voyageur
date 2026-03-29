from typing import Protocol, runtime_checkable

from voyageur.models import Waypoint


@runtime_checkable
class CartographyProvider(Protocol):
    """Interface for cartographic data providers."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        """Return True if any segment of the route crosses land or shallow water."""
        ...
