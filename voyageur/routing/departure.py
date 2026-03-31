import dataclasses
import datetime

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import BoatProfile, Route, WindCondition
from voyageur.routing.isochrone import IsochroneRoutePlanner
from voyageur.tidal.protocol import TidalProvider


@dataclasses.dataclass
class DepartureResult:
    optimal_departure: datetime.datetime
    optimal_route: Route
    baseline_departure: datetime.datetime
    baseline_route: Route
    time_saved: datetime.timedelta


class OptimalDeparturePlanner:
    """Scans a departure window and returns the time with shortest passage duration."""

    def __init__(self, tidal: TidalProvider, cartography: CartographyProvider) -> None:
        self._tidal = tidal
        self._cartography = cartography

    def scan(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        window_start: datetime.datetime,
        window_end: datetime.datetime,
        baseline_departure: datetime.datetime,
        wind: WindCondition,
        boat: BoatProfile,
        scan_interval_minutes: int = 30,
        step_minutes: int = 15,
    ) -> DepartureResult:
        planner = IsochroneRoutePlanner(self._tidal, self._cartography)
        step = datetime.timedelta(minutes=scan_interval_minutes)

        best_t = window_start
        best_route = planner.compute(
            origin=origin,
            destination=destination,
            departure_time=window_start,
            wind=wind,
            boat=boat,
            step_minutes=step_minutes,
        )

        t = window_start + step
        while t <= window_end:
            route = planner.compute(
                origin=origin,
                destination=destination,
                departure_time=t,
                wind=wind,
                boat=boat,
                step_minutes=step_minutes,
            )
            if route.total_duration < best_route.total_duration:
                best_t = t
                best_route = route
            t += step

        baseline_route = planner.compute(
            origin=origin,
            destination=destination,
            departure_time=baseline_departure,
            wind=wind,
            boat=boat,
            step_minutes=step_minutes,
        )
        time_saved = baseline_route.total_duration - best_route.total_duration

        return DepartureResult(
            optimal_departure=best_t,
            optimal_route=best_route,
            baseline_departure=baseline_departure,
            baseline_route=baseline_route,
            time_saved=time_saved,
        )
