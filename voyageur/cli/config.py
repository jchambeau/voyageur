import pathlib

import typer
import yaml

config_app = typer.Typer(
    name="config", help="Manage saved boat profile.", invoke_without_command=True
)


def _profile_path() -> pathlib.Path:
    """Return path to saved boat profile (computed at call time for test isolation)."""
    return pathlib.Path.home() / ".voyageur" / "boat.yaml"


def _load_existing() -> dict:
    """Load existing profile YAML, or return empty dict if absent/corrupt."""
    path = _profile_path()
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


@config_app.callback()
def manage(
    name: str | None = typer.Option(None, "--name", help="Boat name"),
    loa: float | None = typer.Option(None, "--loa", help="Length overall (m)", min=0.0),
    draft: float | None = typer.Option(None, "--draft", help="Draft (m)", min=0.0),
    sail_area: float | None = typer.Option(
        None, "--sail-area", help="Sail area (m²)", min=0.0
    ),
    default_step: int | None = typer.Option(
        None, "--default-step", help="Default time step (min)", min=1
    ),
    show: bool = typer.Option(False, "--show", help="Display saved profile"),
) -> None:
    """Create or update the persistent boat profile."""
    if show:
        path = _profile_path()
        if not path.exists():
            typer.echo("✗ No profile found at ~/.voyageur/boat.yaml", err=True)
            raise typer.Exit(1)
        typer.echo(path.read_text(encoding="utf-8"))
        return

    if all(v is None for v in [name, loa, draft, sail_area, default_step]):
        typer.echo(
            "✗ Provide at least one field to save (or --show to display).",
            err=True,
        )
        raise typer.Exit(1)

    existing = _load_existing()
    # Start from all existing keys (preserves max_wind_kn, max_current_kn, etc.)
    merged = dict(existing)
    merged["name"] = name if name is not None else existing.get("name", "Default")
    merged["loa"] = loa if loa is not None else existing.get("loa", 12.0)
    merged["draft"] = draft if draft is not None else existing.get("draft", 1.8)
    merged["sail_area"] = (
        sail_area if sail_area is not None else existing.get("sail_area", 65.0)
    )
    merged["default_step"] = (
        default_step if default_step is not None else existing.get("default_step", 15)
    )

    path = _profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(merged, default_flow_style=False), encoding="utf-8")
    typer.echo(f"✓ Profile saved to {path}")
