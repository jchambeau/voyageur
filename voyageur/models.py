import datetime
from dataclasses import dataclass, field


@dataclass(slots=True)
class BoatProfile:
    """Persistent boat configuration."""

    name: str
    loa: float           # length overall in metres
    draft: float         # draft in metres
    sail_area: float     # sail area in m²
    default_step: int    # default time step in minutes (1, 5, 15, 30, 60)


@dataclass(slots=True)
class Waypoint:
    """A single step in a computed route."""

    lat: float                    # WGS84 latitude, decimal degrees
    lon: float                    # WGS84 longitude, decimal degrees
    timestamp: datetime.datetime  # UTC timestamp for this step
    heading: float                # true heading in degrees [0, 360)
    speed_over_ground: float      # SOG in knots
    tidal_current_speed: float = 0.0       # current speed in knots (Story 3.2)
    tidal_current_direction: float = 0.0   # current direction in degrees (Story 3.2)
    flagged: bool = False                  # safety threshold exceeded (Story 3.2)


@dataclass(slots=True)
class TidalState:
    """Tidal conditions at a given position and timestamp."""

    timestamp: datetime.datetime  # UTC timestamp
    current_direction: float      # direction current flows TO, degrees [0, 360)
    current_speed: float          # current speed in knots
    water_height: float           # metres above chart datum


@dataclass(slots=True)
class WindCondition:
    """Wind conditions at a given timestamp."""

    timestamp: datetime.datetime  # UTC timestamp
    direction: float              # direction wind blows FROM, degrees [0, 360)
    speed: float                  # wind speed in knots


@dataclass(slots=True)
class Route:
    """A complete computed route."""

    departure_time: datetime.datetime
    waypoints: list[Waypoint] = field(default_factory=list)
    total_duration: datetime.timedelta = field(default_factory=datetime.timedelta)


@dataclass(slots=True)
class SafetyThresholds:
    """Safety threshold parameters for route evaluation."""

    max_wind_kn: float | None = None
    max_current_kn: float | None = None
    max_dist_shelter_nm: float | None = None  # not implemented in MVP
