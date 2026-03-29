import datetime
import math

from pyproj import Geod

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import BoatProfile, Route, Waypoint, WindCondition
from voyageur.tidal.protocol import TidalProvider

KNOTS_TO_MPS: float = 0.514444        # 1 knot = 0.514444 m/s
ARRIVAL_TOLERANCE_M: float = 500.0    # destination reached within 500 m
MAX_STEPS: int = 2000                  # safety limit — prevent infinite loop

_GEOD: Geod = Geod(ellps="WGS84")    # module-level; stateless, safe to share


def _polar_fraction(wind_angle_deg: float) -> float:
    """Return boat speed fraction of wind speed based on True Wind Angle [0, 180]."""
    a = min(abs(wind_angle_deg), 180.0)
    if a < 45.0:     # in irons — cannot sail
        return 0.0
    elif a < 90.0:   # close-hauled
        return 0.45
    elif a < 135.0:  # beam reach (fastest point of sail)
        return 0.50
    else:            # broad reach / running
        return 0.40


class RoutePlanner:
    """Direct propagation routing algorithm combining wind and tidal current vectors."""

    def __init__(
        self,
        tidal: TidalProvider,
        cartography: CartographyProvider,
    ) -> None:
        self._tidal = tidal
        self._cartography = cartography

    def compute(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        departure_time: datetime.datetime,
        wind: WindCondition,
        boat: BoatProfile,
        step_minutes: int = 15,
    ) -> Route:
        """Compute a time-stepped direct route from origin to destination.

        Args:
            origin: (lat, lon) WGS84 departure point.
            destination: (lat, lon) WGS84 arrival point.
            departure_time: UTC timezone-aware departure timestamp.
            wind: constant wind conditions for the passage (MVP).
            boat: boat profile (used for future polar model extension).
            step_minutes: time step in minutes (1, 5, 15, 30, 60).

        Returns:
            Route with one Waypoint per step; total_duration set at completion.
        """
        route = Route(departure_time=departure_time)
        step_sec = step_minutes * 60
        current_lat, current_lon = origin
        current_time = departure_time

        # Check if already at destination before the loop
        _, _, init_dist = _GEOD.inv(
            current_lon, current_lat, destination[1], destination[0]
        )
        if init_dist <= ARRIVAL_TOLERANCE_M:
            route.waypoints.append(
                Waypoint(
                    lat=current_lat,
                    lon=current_lon,
                    timestamp=current_time,
                    heading=0.0,
                    speed_over_ground=0.0,
                )
            )
            route.total_duration = datetime.timedelta(0)
            return route

        for _ in range(MAX_STEPS):
            # 1. Tidal current at current position + timestamp
            tidal_state = self._tidal.get_current(
                current_lat, current_lon, current_time
            )

            # 2. Bearing to destination — normalize fwd_az to [0, 360)
            fwd_az, _, _ = _GEOD.inv(
                current_lon, current_lat, destination[1], destination[0]
            )
            heading = fwd_az % 360.0

            # 3. True Wind Angle → simplified polar fraction → BTW (knots)
            twa = (wind.direction - heading) % 360.0
            if twa > 180.0:
                twa = 360.0 - twa
            btw = wind.speed * _polar_fraction(twa)

            # 4. Vector addition: boat velocity + tidal current → SOG + COG
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

            # 5. Record Waypoint at current position (before advancing)
            route.waypoints.append(
                Waypoint(
                    lat=current_lat,
                    lon=current_lon,
                    timestamp=current_time,
                    heading=heading,
                    speed_over_ground=sog,
                )
            )

            # 6. Advance position
            current_time += datetime.timedelta(seconds=step_sec)
            distance_m = sog * KNOTS_TO_MPS * step_sec
            if distance_m > 0.0:
                new_lon, new_lat, _ = _GEOD.fwd(
                    current_lon, current_lat, cog, distance_m
                )
                current_lon, current_lat = new_lon, new_lat

            # 7. Check arrival at new position
            _, _, remaining_m = _GEOD.inv(
                current_lon, current_lat, destination[1], destination[0]
            )
            if remaining_m <= ARRIVAL_TOLERANCE_M:
                route.waypoints.append(
                    Waypoint(
                        lat=current_lat,
                        lon=current_lon,
                        timestamp=current_time,
                        heading=heading,
                        speed_over_ground=sog,
                    )
                )
                break

        route.total_duration = current_time - departure_time
        return route
