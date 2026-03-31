import datetime
from typing import Protocol, runtime_checkable

from voyageur.models import WindCondition


@runtime_checkable
class WeatherProvider(Protocol):
    """Interface for weather/wind forecast providers."""

    def get_wind(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> WindCondition:
        """Return wind forecast at the given WGS84 position and UTC timestamp."""
        ...
