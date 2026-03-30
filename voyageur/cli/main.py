import dataclasses
import datetime
import re

import typer

from voyageur.cli.config import config_app
from voyageur.models import BoatProfile, SafetyThresholds, WindCondition

app = typer.Typer(
    name="voyageur",
    help="Sailing route planner for the Norman coast.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

PORTS: dict[str, tuple[float, float]] = {
    "cherbourg":             (49.6453, -1.6222),
    "granville":             (48.8327, -1.5971),
    "le havre":              (49.4892,  0.1080),
    "saint-malo":            (48.6490, -1.9800),
    "st-malo":               (48.6490, -1.9800),
    "barfleur":              (49.6733, -1.2638),
    "saint-vaast-la-hougue": (49.5875, -1.2703),
    "honfleur":              (49.4189,  0.2337),
}

_LATLON_RE = re.compile(r"^(\d+\.?\d*)([NS])/(\d+\.?\d*)([EW])$", re.IGNORECASE)
_WIND_RE = re.compile(r"^\d{1,3}/\d+(\.\d+)?$")

_DEFAULT_BOAT = BoatProfile(
    name="Default", loa=12.0, draft=1.8, sail_area=65.0, default_step=15
)



def _parse_position(s: str) -> tuple[float, float] | None:
    """Parse port name or latN/lonW string. Returns (lat, lon) or None."""
    key = s.strip().lower()
    if key in PORTS:
        return PORTS[key]
    m = _LATLON_RE.match(s.strip())
    if m:
        lat = float(m.group(1)) * (1 if m.group(2).upper() == "N" else -1)
        lon = float(m.group(3)) * (1 if m.group(4).upper() == "E" else -1)
        return lat, lon
    return None


def _parse_wind(s: str, timestamp: datetime.datetime) -> WindCondition | None:
    """Parse 'DIR/SPD' string. Returns WindCondition or None."""
    if not _WIND_RE.match(s.strip()):
        return None
    parts = s.strip().split("/")
    direction = float(parts[0])
    if direction >= 360.0:
        return None
    return WindCondition(
        timestamp=timestamp,
        direction=direction,
        speed=float(parts[1]),
    )


def _parse_depart(s: str) -> datetime.datetime | None:
    """Parse ISO 8601 string to UTC-aware datetime. Returns None on error."""
    try:
        dt = datetime.datetime.fromisoformat(s.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError:
        return None


def _load_boat() -> tuple[BoatProfile, bool, dict[str, float]]:
    """Load boat profile from ~/.voyageur/boat.yaml.

    Returns (profile, loaded, thresholds_dict).
    thresholds_dict may contain 'max_wind_kn' and/or 'max_current_kn'.
    """
    import pathlib

    import yaml as _yaml

    path = pathlib.Path.home() / ".voyageur" / "boat.yaml"
    if not path.exists():
        return _DEFAULT_BOAT, False, {}
    try:
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("boat.yaml is empty or not a YAML mapping")
        thresholds: dict[str, float] = {}
        for key in ("max_wind_kn", "max_current_kn"):
            if key in data:
                thresholds[key] = float(data[key])
        return (
            BoatProfile(
                name=data.get("name", "Default"),
                loa=float(data["loa"]),
                draft=float(data["draft"]),
                sail_area=float(data["sail_area"]),
                default_step=int(data.get("default_step", 15)),
            ),
            True,
            thresholds,
        )
    except (KeyError, TypeError, ValueError, OSError, ImportError, _yaml.YAMLError):
        return _DEFAULT_BOAT, False, {}


@app.command()
def plan(
    from_port: str = typer.Option(..., "--from", help="Departure port or lat/lon"),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    depart: str = typer.Option(..., "--depart", help="Departure time (ISO 8601)"),
    wind: str = typer.Option(..., "--wind", help="Wind direction/speed (e.g. 240/15)"),
    step: int = typer.Option(15, "--step", help="Time step in minutes (1,5,15,30,60)"),
    max_wind: float | None = typer.Option(
        None, "--max-wind", help="Max wind speed (kn)", min=0.0
    ),
    max_current: float | None = typer.Option(
        None, "--max-current", help="Max tidal current speed (kn)", min=0.0
    ),
    max_dist_shelter: float | None = typer.Option(
        None, "--max-dist-shelter", help="Max distance from shelter (NM)"
    ),
    draft: float | None = typer.Option(
        None, "--draft", help="Override saved boat draft (m)", min=0.0
    ),
    criteria: str | None = typer.Option(
        None,
        "--criteria",
        help="Route criteria: fastest,comfort,shelter,traffic or all",
    ),
) -> None:
    """Plan a sailing passage between two Norman coast ports."""
    departure_time = _parse_depart(depart)
    if departure_time is None:
        typer.echo(f"✗ Invalid departure time: {depart!r}", err=True)
        raise typer.Exit(1)

    origin = _parse_position(from_port)
    if origin is None:
        typer.echo(f"✗ Unknown port or invalid position: {from_port!r}", err=True)
        raise typer.Exit(1)

    destination = _parse_position(to_port)
    if destination is None:
        typer.echo(f"✗ Unknown port or invalid position: {to_port!r}", err=True)
        raise typer.Exit(1)

    if step not in (1, 5, 15, 30, 60):
        typer.echo(
            f"✗ --step must be one of 1, 5, 15, 30, 60 (got {step})",
            err=True,
        )
        raise typer.Exit(1)

    wind_condition = _parse_wind(wind, departure_time)
    if wind_condition is None:
        typer.echo(
            f"✗ Invalid wind format: {wind!r}. Expected DIR/SPD (e.g. 240/15)",
            err=True,
        )
        raise typer.Exit(1)

    boat, loaded, boat_thresholds = _load_boat()
    if draft is not None:
        boat = dataclasses.replace(boat, draft=draft)
    if not loaded:
        typer.echo(
            "⚠ No boat profile found at ~/.voyageur/boat.yaml — using defaults.",
            err=True,
        )

    if max_dist_shelter is not None:
        typer.echo(
            "⚠ --max-dist-shelter not yet implemented — shelter data unavailable.",
            err=True,
        )

    thresholds = SafetyThresholds(
        max_wind_kn=(
            max_wind if max_wind is not None
            else boat_thresholds.get("max_wind_kn")
        ),
        max_current_kn=(
            max_current if max_current is not None
            else boat_thresholds.get("max_current_kn")
        ),
    )

    from voyageur.cartography.impl import GeoJsonCartography
    from voyageur.output.formatter import format_multi_criteria, format_timeline
    from voyageur.routing.isochrone import IsochroneRoutePlanner
    from voyageur.routing.multi import CRITERIA as _ALL_CRITERIA
    from voyageur.routing.multi import MultiCriteriaRoutePlanner
    from voyageur.routing.safety import evaluate_route
    from voyageur.tidal.impl import HarmonicTidalModel

    # Parse --criteria option.
    criteria_list: list[str] | None = None
    if criteria is not None:
        raw = (
            list(_ALL_CRITERIA)
            if criteria.strip() == "all"
            else [c.strip() for c in criteria.split(",")]
        )
        invalid = [c for c in raw if c not in _ALL_CRITERIA]
        if invalid:
            typer.echo(
                f"✗ Unknown criteria: {', '.join(invalid)}."
                f" Valid: {', '.join(_ALL_CRITERIA)}",
                err=True,
            )
            raise typer.Exit(1)
        if "traffic" in raw:
            typer.echo(
                "⚠ traffic: no shipping lane data — falls back to fastest",
                err=True,
            )
        criteria_list = raw

    cartography = GeoJsonCartography()
    tidal = HarmonicTidalModel()

    if criteria_list is not None:
        multi = MultiCriteriaRoutePlanner(tidal=tidal, cartography=cartography)
        results = multi.compute_all(
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
            criteria=criteria_list,
        )
        for route in results.values():
            evaluate_route(route, wind_condition, thresholds)
        first_route = next(iter(results.values()))
        if len(first_route.waypoints) > 0 and all(
            wp.flagged for wp in first_route.waypoints
        ):
            typer.echo(
                "✗ No viable conditions — all segments exceed safety thresholds.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(format_multi_criteria(results, wind=wind_condition))
    else:
        planner = IsochroneRoutePlanner(tidal=tidal, cartography=cartography)
        route = planner.compute(
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
        )
        flag_count = evaluate_route(route, wind_condition, thresholds)
        if flag_count > 0 and flag_count == len(route.waypoints):
            typer.echo(
                "✗ No viable conditions — all segments exceed safety thresholds.",
                err=True,
            )
            raise typer.Exit(1)
        if cartography.intersects_land(route.waypoints):
            pos_hint = ""
            for a, b in zip(route.waypoints[:-1], route.waypoints[1:]):
                if cartography.intersects_land([a, b]):
                    mid_lat = (a.lat + b.lat) / 2
                    mid_lon = (a.lon + b.lon) / 2
                    ew = "W" if mid_lon < 0 else "E"
                    pos_hint = (
                        f" (approx. {mid_lat:.2f}°N/{abs(mid_lon):.2f}°{ew})"
                    )
                    break
            typer.echo(
                f"⚠ Route crosses land or shallow water{pos_hint}"
                " — check your passage plan.",
                err=True,
            )
        typer.echo(format_timeline(route, wind=wind_condition))
