import datetime
import math

from pyproj import Geod

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import BoatProfile, Route, Waypoint, WindCondition
from voyageur.routing.planner import (
    ARRIVAL_TOLERANCE_M,
    KNOTS_TO_MPS,
    MAX_STEPS,
    _polar_fraction,
)
from voyageur.tidal.protocol import TidalProvider

# Heading offsets tried in order: direct first, then symmetric deviations.
_HEADING_OFFSETS: tuple[float, ...] = (
    0.0,
    15.0, -15.0,
    30.0, -30.0,
    45.0, -45.0,
    60.0, -60.0,
    75.0, -75.0,
    90.0, -90.0,
)

_GEOD: Geod = Geod(ellps="WGS84")


class IsochroneRoutePlanner:
    """Heading-beam routing that avoids land by deviating from the direct bearing.

    At each time step the algorithm tries the direct bearing first, then
    symmetric offsets (±15°, ±30°, … ±90°) until a segment free of land
    intersection is found.  Falls back to the direct bearing if all candidates
    are blocked (degenerate case: surrounded by land on GeoJSON data).
    """

    def __init__(
        self,
        tidal: TidalProvider,
        cartography: CartographyProvider,
    ) -> None:
        self._tidal = tidal
        self._cartography = cartography

    def _segment_crosses_land(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        timestamp: datetime.datetime,
    ) -> bool:
        """Return True if the segment (lat1,lon1)→(lat2,lon2) crosses land."""
        a = Waypoint(
            lat=lat1,
            lon=lon1,
            timestamp=timestamp,
            heading=0.0,
            speed_over_ground=0.0,
        )
        b = Waypoint(
            lat=lat2,
            lon=lon2,
            timestamp=timestamp,
            heading=0.0,
            speed_over_ground=0.0,
        )
        return self._cartography.intersects_land([a, b])

    def compute(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure_time: datetime.datetime,
        wind: WindCondition,
        boat: BoatProfile,
        step_minutes: int = 15,
    ) -> Route:
        """Compute a time-stepped route from origin to destination, avoiding land.

        Args:
            origin: (lat, lon) WGS84 departure point.
            destination: (lat, lon) WGS84 arrival point.
            departure_time: UTC timezone-aware departure timestamp.
            wind: constant wind conditions for the passage.
            boat: boat profile (used for polar model).
            step_minutes: time step in minutes (1, 5, 15, 30, 60).

        Returns:
            Route with one Waypoint per step; total_duration set at completion.
        """
        route = Route(departure_time=departure_time)
        step_sec = step_minutes * 60
        current_lat, current_lon = origin
        current_time = departure_time

        # Check if already at destination before the loop.
        _, _, init_dist = _GEOD.inv(
            current_lon, current_lat, destination[1], destination[0]
        )
        if init_dist <= ARRIVAL_TOLERANCE_M:
            tidal_state = self._tidal.get_current(
                current_lat, current_lon, current_time
            )
            route.waypoints.append(
                Waypoint(
                    lat=current_lat,
                    lon=current_lon,
                    timestamp=current_time,
                    heading=0.0,
                    speed_over_ground=0.0,
                    tidal_current_speed=tidal_state.current_speed,
                    tidal_current_direction=tidal_state.current_direction,
                )
            )
            route.total_duration = datetime.timedelta(0)
            return route

        for _ in range(MAX_STEPS):
            # 1. Tidal current at current position + timestamp.
            tidal_state = self._tidal.get_current(
                current_lat, current_lon, current_time
            )

            # 2. Direct bearing to destination.
            fwd_az, _, _ = _GEOD.inv(
                current_lon, current_lat, destination[1], destination[0]
            )
            direct_bearing = fwd_az % 360.0

            # 3. Boat speed from polar model (TWA relative to direct bearing).
            twa = (wind.direction - direct_bearing) % 360.0
            if twa > 180.0:
                twa = 360.0 - twa
            btw = wind.speed * _polar_fraction(twa)

            # 4. Beam search: pick first heading whose next segment avoids land.
            heading = direct_bearing  # fallback if all candidates blocked
            distance_m = btw * KNOTS_TO_MPS * step_sec
            if distance_m > 0.0:
                for offset in _HEADING_OFFSETS:
                    candidate = (direct_bearing + offset) % 360.0
                    cand_lon, cand_lat, _ = _GEOD.fwd(
                        current_lon, current_lat, candidate, distance_m
                    )
                    if not self._segment_crosses_land(
                        current_lat, current_lon, cand_lat, cand_lon, current_time
                    ):
                        heading = candidate
                        break

            # 5. Vector addition: boat velocity + tidal current → SOG + COG.
            boat_n = btw * math.cos(math.radians(heading))
            boat_e = btw * math.sin(math.radians(heading))
            tide_n = tidal_state.current_speed * math.cos(
                math.radians(tidal_state.current_direction)
            )
            tide_e = tidal_state.current_speed * math.sin(
                math.radians(tidal_state.current_direction)
            )
            total_n = boat_n + tide_n
            total_e = boat_e + tide_e
            sog = math.hypot(total_n, total_e)
            cog = math.degrees(math.atan2(total_e, total_n)) % 360.0

            # 6. Record Waypoint at current position (before advancing).
            route.waypoints.append(
                Waypoint(
                    lat=current_lat,
                    lon=current_lon,
                    timestamp=current_time,
                    heading=heading,
                    speed_over_ground=sog,
                    tidal_current_speed=tidal_state.current_speed,
                    tidal_current_direction=tidal_state.current_direction,
                )
            )

            # 7. Advance position along COG.
            current_time += datetime.timedelta(seconds=step_sec)
            if sog > 0.0:
                new_lon, new_lat, _ = _GEOD.fwd(
                    current_lon, current_lat, cog, sog * KNOTS_TO_MPS * step_sec
                )
                current_lon, current_lat = new_lon, new_lat

            # 8. Check arrival at new position.
            _, _, remaining_m = _GEOD.inv(
                current_lon, current_lat, destination[1], destination[0]
            )
            if remaining_m <= ARRIVAL_TOLERANCE_M:
                arrival_tidal = self._tidal.get_current(
                    current_lat, current_lon, current_time
                )
                route.waypoints.append(
                    Waypoint(
                        lat=current_lat,
                        lon=current_lon,
                        timestamp=current_time,
                        heading=heading,
                        speed_over_ground=sog,
                        tidal_current_speed=arrival_tidal.current_speed,
                        tidal_current_direction=arrival_tidal.current_direction,
                    )
                )
                break

        route.total_duration = current_time - departure_time
        return route
