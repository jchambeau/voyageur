import datetime
import sys

import httpx

from voyageur.models import TidalState
from voyageur.tidal.impl import HarmonicTidalModel
from voyageur.tidal.protocol import TidalProvider

SHOM_API_URL: str = "https://services.data.shom.fr/hdm/tidal/current"


class ShomTidalClient:
    """TidalProvider that queries the SHOM API with HarmonicTidalModel fallback."""

    def __init__(
        self,
        api_key: str,
        fallback: TidalProvider | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._fallback: TidalProvider = fallback or HarmonicTidalModel()
        self._http = http_client or httpx.Client(timeout=10.0)

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        """Return tidal state from SHOM API; fallback to harmonic model on error."""
        try:
            resp = self._http.get(
                SHOM_API_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "datetime": at.isoformat(),
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return TidalState(
                timestamp=at,
                current_direction=float(data["direction"]),
                current_speed=float(data["speed"]),
                water_height=float(data.get("height", 0.0)),
            )
        except Exception:
            sys.stderr.write(
                "⚠ SHOM API unavailable — using embedded harmonic model\n"
            )
            return self._fallback.get_current(lat, lon, at)
