import datetime
from typing import Protocol, runtime_checkable

from voyageur.models import TidalState


@runtime_checkable
class TidalProvider(Protocol):
    """Interface for tidal data providers."""

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        """Return tidal state at the given WGS84 position and UTC timestamp."""
        ...
