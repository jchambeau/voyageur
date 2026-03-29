from voyageur.models import Route, SafetyThresholds, WindCondition


def evaluate_route(
    route: Route,
    wind: WindCondition,
    thresholds: SafetyThresholds,
) -> int:
    """Flag waypoints exceeding safety thresholds. Returns flagged count.

    Mutates route.waypoints[*].flagged in place.
    """
    count = 0
    for wp in route.waypoints:
        flagged = False
        if (
            thresholds.max_wind_kn is not None
            and wind.speed > thresholds.max_wind_kn
        ):
            flagged = True
        if (
            thresholds.max_current_kn is not None
            and wp.tidal_current_speed > thresholds.max_current_kn
        ):
            flagged = True
        wp.flagged = flagged
        if flagged:
            count += 1
    return count
