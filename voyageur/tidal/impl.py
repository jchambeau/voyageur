import datetime
import importlib.resources
import math

import yaml
from pyproj import Geod

from voyageur.models import TidalState

OMEGA_M2: float = 28.9841042   # degrees per hour
OMEGA_S2: float = 30.0000000   # degrees per hour
EPOCH: datetime.datetime = datetime.datetime(1900, 1, 1, tzinfo=datetime.timezone.utc)
MIN_DIST_KM: float = 0.1       # avoid division by zero in IDW


class HarmonicTidalModel:
    """Harmonic tidal model using M2/S2 constituents from embedded YAML data."""

    def __init__(self) -> None:
        self._ports: dict = self._load_ports()
        self._geod: Geod = Geod(ellps="WGS84")

    def _load_ports(self) -> dict:
        """Load reference port harmonic constants from embedded YAML."""
        ref = importlib.resources.files("voyageur.tidal") / "data" / "ports.yaml"
        with ref.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)["ports"]

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        """Return tidal state at the given WGS84 position and UTC timestamp."""
        hours = (at - EPOCH).total_seconds() / 3600.0
        amp_m2, phase_m2, amp_s2, phase_s2, flood_dir = self._interpolate(lat, lon)
        speed = (
            amp_m2 * math.cos(math.radians(OMEGA_M2 * hours - phase_m2))
            + amp_s2 * math.cos(math.radians(OMEGA_S2 * hours - phase_s2))
        )
        direction = flood_dir if speed >= 0.0 else (flood_dir + 180.0) % 360.0
        return TidalState(
            timestamp=at,
            current_direction=round(direction, 1),
            current_speed=round(abs(speed), 3),
            water_height=0.0,
        )

    def _interpolate(
        self, lat: float, lon: float
    ) -> tuple[float, float, float, float, float]:
        """IDW interpolation of harmonic constants from reference ports."""
        weights = []
        for port in self._ports.values():
            _, _, dist_m = self._geod.inv(lon, lat, port["lon"], port["lat"])
            dist_km = max(dist_m / 1000.0, MIN_DIST_KM)
            weights.append(1.0 / dist_km**2)
        total_w = sum(weights)
        norm_w = [w / total_w for w in weights]

        ports = list(self._ports.values())
        amp_m2 = sum(w * p["M2"]["amplitude"] for w, p in zip(norm_w, ports))
        amp_s2 = sum(w * p["S2"]["amplitude"] for w, p in zip(norm_w, ports))
        phase_m2 = self._circular_mean([p["M2"]["phase"] for p in ports], norm_w)
        phase_s2 = self._circular_mean([p["S2"]["phase"] for p in ports], norm_w)
        flood_dir = self._circular_mean([p["flood_direction"] for p in ports], norm_w)
        return amp_m2, phase_m2, amp_s2, phase_s2, flood_dir

    @staticmethod
    def _circular_mean(angles_deg: list[float], weights: list[float]) -> float:
        """Weighted circular mean of angles in degrees."""
        sin_sum = sum(
            w * math.sin(math.radians(a)) for w, a in zip(weights, angles_deg)
        )
        cos_sum = sum(
            w * math.cos(math.radians(a)) for w, a in zip(weights, angles_deg)
        )
        return math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0
