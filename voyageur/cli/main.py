import dataclasses
import datetime
import re

import typer

from voyageur.cli.config import config_app
from voyageur.models import BoatProfile, SafetyThresholds, WindCondition
from voyageur.tidal.protocol import TidalProvider

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


def _parse_window(
    s: str,
) -> tuple[datetime.datetime, datetime.datetime] | None:
    """Parse 'ISO/ISO' window string. Returns (start, end) or None."""
    parts = s.strip().split("/", 1)
    if len(parts) != 2:
        return None
    start = _parse_depart(parts[0])
    end = _parse_depart(parts[1])
    if start is None or end is None:
        return None
    return start, end


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


def _load_voyageur_config() -> dict:
    """Load ~/.voyageur/config.yaml; return {} if absent or corrupt."""
    import pathlib

    import yaml as _yaml

    path = pathlib.Path.home() / ".voyageur" / "config.yaml"
    if not path.exists():
        return {}
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        typer.echo("⚠ Cannot read ~/.voyageur/config.yaml — using defaults", err=True)
        return {}
    except _yaml.YAMLError:
        return {}


def _build_tidal_provider() -> TidalProvider:
    """Return ShomTidalClient if shom_api_key configured, else HarmonicTidalModel."""
    from voyageur.tidal.impl import HarmonicTidalModel
    from voyageur.tidal.shom_client import ShomTidalClient

    api_key = _load_voyageur_config().get("shom_api_key")
    if isinstance(api_key, str) and api_key:
        return ShomTidalClient(api_key=api_key)
    return HarmonicTidalModel()


def _handle_no_viable(
    origin: tuple[float, float],
    destination: tuple[float, float],
    current_time: datetime.datetime,
    wind: "WindCondition",
    boat: "BoatProfile",
    tidal: object,
    cartography: object,
    thresholds: "SafetyThresholds",
    step_minutes: int,
) -> None:
    """Print ✗ error and scan next 12h for viable departure."""
    from voyageur.routing.isochrone import IsochroneRoutePlanner
    from voyageur.routing.safety import evaluate_route

    typer.echo(
        "✗ No viable conditions — all segments exceed safety thresholds.", err=True
    )
    planner = IsochroneRoutePlanner(tidal, cartography)
    for h in range(1, 13):
        t = current_time + datetime.timedelta(hours=h)
        route = planner.compute(
            origin=origin,
            destination=destination,
            departure_time=t,
            wind=wind,
            boat=boat,
            step_minutes=step_minutes,
        )
        fc = evaluate_route(route, wind, thresholds)
        if fc < len(route.waypoints):
            typer.echo(
                f"⚠ Next viable departure: {t.strftime('%H:%M')} UTC", err=True
            )
            return
    typer.echo("⚠ No viable route in next 12 hours", err=True)


@app.command()
def plan(
    from_port: str = typer.Option(..., "--from", help="Departure port or lat/lon"),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    depart: str = typer.Option(..., "--depart", help="Departure time (ISO 8601)"),
    wind: str | None = typer.Option(
        None, "--wind", help="Wind direction/speed (e.g. 240/15)"
    ),
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
    optimize_departure: bool = typer.Option(
        False, "--optimize-departure", is_flag=True,
        help="Find optimal departure time in --window",
    ),
    window: str | None = typer.Option(
        None, "--window",
        help="Search window ISO/ISO (e.g. 2026-03-29T06:00/2026-03-29T12:00)",
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

    weather_provider = None
    wind_source: str | None = None

    if wind is None:
        from voyageur.weather.openmeteo import OpenMeteoClient

        _wc = OpenMeteoClient()
        try:
            wind_condition = _wc.get_wind(origin[0], origin[1], departure_time)
        except (OSError, ValueError):
            typer.echo(
                "✗ Weather forecast unavailable — provide --wind manually",
                err=True,
            )
            raise typer.Exit(1)
        weather_provider = _wc
        wind_source = "OpenMeteo"
    else:
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

    # Validate --optimize-departure / --window
    window_range: tuple[datetime.datetime, datetime.datetime] | None = None
    if optimize_departure:
        if window is None:
            typer.echo("✗ --window required with --optimize-departure", err=True)
            raise typer.Exit(1)
        window_range = _parse_window(window)
        if window_range is None:
            typer.echo(
                f"✗ Invalid --window format: {window!r}."
                " Expected ISO/ISO (e.g. 2026-03-29T06:00/2026-03-29T12:00)",
                err=True,
            )
            raise typer.Exit(1)
        if window_range[1] <= window_range[0]:
            typer.echo("✗ --window end must be after start", err=True)
            raise typer.Exit(1)
        if window_range[1] - window_range[0] < datetime.timedelta(minutes=30):
            typer.echo(
                "⚠ --window shorter than 30-minute scan interval"
                " — only departure time will be evaluated.",
                err=True,
            )

    from voyageur.cartography.impl import GeoJsonCartography
    from voyageur.output.formatter import format_multi_criteria, format_timeline
    from voyageur.routing.isochrone import IsochroneRoutePlanner
    from voyageur.routing.multi import CRITERIA as _ALL_CRITERIA
    from voyageur.routing.multi import MultiCriteriaRoutePlanner
    from voyageur.routing.safety import evaluate_route

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

    if optimize_departure and criteria_list is not None:
        typer.echo(
            "✗ --optimize-departure and --criteria are mutually exclusive", err=True
        )
        raise typer.Exit(1)

    cartography = GeoJsonCartography()
    tidal = _build_tidal_provider()

    if optimize_departure:
        from voyageur.routing.departure import OptimalDeparturePlanner

        opt_planner = OptimalDeparturePlanner(tidal=tidal, cartography=cartography)
        result = opt_planner.scan(
            origin=origin,
            destination=destination,
            window_start=window_range[0],
            window_end=window_range[1],
            baseline_departure=departure_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
        )
        opt_flag_count = evaluate_route(
            result.optimal_route, wind_condition, thresholds
        )
        if opt_flag_count > 0 and opt_flag_count == len(result.optimal_route.waypoints):
            typer.echo(
                "✗ No viable conditions — all segments exceed safety thresholds.",
                err=True,
            )
            raise typer.Exit(1)
        if cartography.intersects_land(result.optimal_route.waypoints):
            typer.echo(
                "⚠ Route crosses land or shallow water"
                " — check your passage plan.",
                err=True,
            )
        opt_hhmm = result.optimal_departure.strftime("%H:%M")
        base_hhmm = result.baseline_departure.strftime("%H:%M")
        saved = result.time_saved
        saved_str = (
            f"{int(saved.total_seconds() // 3600):02d}:"
            f"{int((saved.total_seconds() % 3600) // 60):02d}"
        )
        if saved.total_seconds() > 0:
            rec_line = (
                f"Optimal departure: {opt_hhmm} — saving {saved_str} vs {base_hhmm}"
            )
        else:
            rec_line = f"Optimal departure: {opt_hhmm} — no improvement vs {base_hhmm}"
        typer.echo(rec_line)
        typer.echo(
            format_timeline(
                result.optimal_route, wind=wind_condition, wind_source=wind_source
            )
        )
    elif criteria_list is not None:
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
        if results and all(
            len(route.waypoints) > 0 and all(wp.flagged for wp in route.waypoints)
            for route in results.values()
        ):
            typer.echo(
                "✗ No viable conditions — all segments exceed safety thresholds.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(
            format_multi_criteria(results, wind=wind_condition, wind_source=wind_source)
        )
    else:
        planner = IsochroneRoutePlanner(tidal=tidal, cartography=cartography)
        route = planner.compute(
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
            weather=weather_provider,
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
        typer.echo(format_timeline(route, wind=wind_condition, wind_source=wind_source))


@app.command("replan")
def replan(
    from_port: str = typer.Option(
        ..., "--from", help="Current position (port or lat/lon)"
    ),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    current_time_str: str = typer.Option(
        ..., "--time", help="Current time (ISO 8601)"
    ),
    wind: str | None = typer.Option(
        None, "--wind", help="Wind direction/speed (e.g. 240/15)"
    ),
    step: int = typer.Option(15, "--step", help="Time step in minutes (1,5,15,30,60)"),
    max_wind: float | None = typer.Option(
        None, "--max-wind", help="Max wind speed (kn)", min=0.0
    ),
    max_current: float | None = typer.Option(
        None, "--max-current", help="Max tidal current speed (kn)", min=0.0
    ),
    draft: float | None = typer.Option(
        None, "--draft", help="Override boat draft (m)", min=0.0
    ),
    criteria: str | None = typer.Option(
        None,
        "--criteria",
        help="Route criteria: fastest,comfort,shelter,traffic or all",
    ),
) -> None:
    """Re-plan a sailing passage from current position with updated conditions."""
    current_time = _parse_depart(current_time_str)
    if current_time is None:
        typer.echo(f"✗ Invalid time: {current_time_str!r}", err=True)
        raise typer.Exit(1)

    origin = _parse_position(from_port)
    if origin is None:
        typer.echo(
            f"✗ Unknown port or invalid position: {from_port!r}", err=True
        )
        raise typer.Exit(1)

    destination = _parse_position(to_port)
    if destination is None:
        typer.echo(
            f"✗ Unknown port or invalid position: {to_port!r}", err=True
        )
        raise typer.Exit(1)

    if step not in (1, 5, 15, 30, 60):
        typer.echo(
            f"✗ --step must be one of 1, 5, 15, 30, 60 (got {step})", err=True
        )
        raise typer.Exit(1)

    weather_provider = None
    wind_source: str | None = None

    if wind is None:
        from voyageur.weather.openmeteo import OpenMeteoClient

        _wc = OpenMeteoClient()
        try:
            wind_condition = _wc.get_wind(origin[0], origin[1], current_time)
        except (OSError, ValueError):
            typer.echo(
                "✗ Weather forecast unavailable — provide --wind manually",
                err=True,
            )
            raise typer.Exit(1)
        weather_provider = _wc
        wind_source = "OpenMeteo"
    else:
        wind_condition = _parse_wind(wind, current_time)
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
    from voyageur.routing.safety import evaluate_route

    criteria_list: list[str] | None = None
    if criteria is not None:
        from voyageur.routing.multi import CRITERIA as _ALL_CRITERIA

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
    tidal = _build_tidal_provider()

    if criteria_list is not None:
        from voyageur.routing.multi import MultiCriteriaRoutePlanner

        multi = MultiCriteriaRoutePlanner(tidal=tidal, cartography=cartography)
        results = multi.compute_all(
            origin=origin,
            destination=destination,
            departure_time=current_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
            criteria=criteria_list,
        )
        for route in results.values():
            evaluate_route(route, wind_condition, thresholds)
        if results and all(
            len(route.waypoints) > 0 and all(wp.flagged for wp in route.waypoints)
            for route in results.values()
        ):
            _handle_no_viable(
                origin, destination, current_time, wind_condition, boat,
                tidal, cartography, thresholds, step,
            )
            raise typer.Exit(1)
        typer.echo(
            format_multi_criteria(results, wind=wind_condition, wind_source=wind_source)
        )
    else:
        route = IsochroneRoutePlanner(tidal=tidal, cartography=cartography).compute(
            origin=origin,
            destination=destination,
            departure_time=current_time,
            wind=wind_condition,
            boat=boat,
            step_minutes=step,
            weather=weather_provider,
        )
        flag_count = evaluate_route(route, wind_condition, thresholds)
        if flag_count > 0 and flag_count == len(route.waypoints):
            _handle_no_viable(
                origin, destination, current_time, wind_condition, boat,
                tidal, cartography, thresholds, step,
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
        typer.echo(
            format_timeline(route, wind=wind_condition, wind_source=wind_source)
        )
