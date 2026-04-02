import datetime

import httpx

from voyageur.models import WindCondition

OPENMETEO_URL: str = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoClient:
    """WeatherProvider using the OpenMeteo public API (no API key required)."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http = http_client or httpx.Client(timeout=10.0)
        self._forecast: list[WindCondition] = []

    def get_wind(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> WindCondition:
        """Return wind at given position/time from cached hourly forecast."""
        if not self._forecast:
            self._fetch(lat, lon, at)
        if not self._forecast:
            raise ValueError("OpenMeteo returned an empty forecast")
        # Normalize to naive for comparison (pipeline uses naive datetimes).
        naive_at = at.replace(tzinfo=None) if at.tzinfo is not None else at
        return min(
            self._forecast,
            key=lambda w: abs((w.timestamp - naive_at).total_seconds()),
        )

    def _fetch(self, lat: float, lon: float, at: datetime.datetime) -> None:
        """Fetch 24h hourly wind forecast from OpenMeteo and populate cache."""
        start = at.date().isoformat()
        end = (at + datetime.timedelta(days=1)).date().isoformat()
        try:
            resp = self._http.get(
                OPENMETEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "windspeed_10m,winddirection_10m",
                    "wind_speed_unit": "kn",
                    "timezone": "UTC",
                    "start_date": start,
                    "end_date": end,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            times = data["hourly"]["time"]
            speeds = data["hourly"]["windspeed_10m"]
            directions = data["hourly"]["winddirection_10m"]
            self._forecast = [
                WindCondition(
                    timestamp=datetime.datetime.fromisoformat(t),
                    direction=float(d),
                    speed=float(s),
                )
                for t, s, d in zip(times, speeds, directions)
                if s is not None and d is not None
            ]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ValueError(f"OpenMeteo forecast unavailable: {exc}") from exc
