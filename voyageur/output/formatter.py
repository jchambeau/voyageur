import datetime

from pyproj import Geod

from voyageur.models import Route, Waypoint, WindCondition

_GEOD: Geod = Geod(ellps="WGS84")

SEP = "  "
HEADER = SEP.join(
    ["TIME ", "LAT    ", "LON     ", "HDG ", "SOG   ", "TIDE   ", "WIND    "]
)
DIVIDER = "-" * len(HEADER)


def _elapsed(wp_timestamp: datetime.datetime, departure_time: datetime.datetime) -> str:
    """Return elapsed time as HH:MM."""
    total_sec = int((wp_timestamp - departure_time).total_seconds())
    h, rem = divmod(total_sec, 3600)
    m = rem // 60
    return f"{h:02d}:{m:02d}"


def _fmt_lat(lat: float) -> str:
    """Format latitude as NNN.NNNx (7 chars)."""
    hem = "N" if lat >= 0.0 else "S"
    return f"{abs(lat):6.3f}{hem}"


def _fmt_lon(lon: float) -> str:
    """Format longitude as NNN.NNNx (8 chars)."""
    hem = "E" if lon >= 0.0 else "W"
    return f"{abs(lon):7.3f}{hem}"


def _fmt_hdg(hdg: float) -> str:
    """Format heading as NNN° (4 chars)."""
    return f"{int(hdg):3d}\u00b0"


def _fmt_sog(sog: float) -> str:
    """Format SOG as NN.Nkn (6 chars)."""
    return f"{sog:4.1f}kn"


def _fmt_dir_spd(direction: float, speed: float) -> str:
    """Format direction/speed as NNN/NN.N (up to 8 chars)."""
    return f"{direction:3.0f}/{speed:.1f}"


def _total_distance_nm(waypoints: list[Waypoint]) -> float:
    """Compute total route distance in nautical miles."""
    if len(waypoints) < 2:
        return 0.0
    total_m = 0.0
    for a, b in zip(waypoints[:-1], waypoints[1:]):
        _, _, dist_m = _GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        total_m += dist_m
    return total_m / 1852.0


def _fmt_duration(td: datetime.timedelta) -> str:
    """Format timedelta as 'Xh Ym'."""
    total_min = int(td.total_seconds() / 60)
    h, m = divmod(total_min, 60)
    return f"{h}h {m:02d}m"


def format_timeline(route: Route, wind: WindCondition | None = None) -> str:
    """Format a computed route as an 80-column ASCII timeline table."""
    lines: list[str] = [HEADER, DIVIDER]
    for wp in route.waypoints:
        elapsed = _elapsed(wp.timestamp, route.departure_time)
        lat = _fmt_lat(wp.lat)
        lon = _fmt_lon(wp.lon)
        hdg = _fmt_hdg(wp.heading)
        sog = _fmt_sog(wp.speed_over_ground)
        tide = "---/---"
        if wind is not None:
            wind_col = _fmt_dir_spd(wind.direction, wind.speed)
        else:
            wind_col = "---/---"
        row = SEP.join([elapsed, lat, lon, hdg, sog, tide, wind_col])
        lines.append(row)
    lines.append(DIVIDER)

    dist_nm = _total_distance_nm(route.waypoints)
    duration_str = _fmt_duration(route.total_duration)
    lines.append(f"Total: {dist_nm:.1f} NM  |  Duration: {duration_str}  |  Flags: 0")
    return "\n".join(lines)
