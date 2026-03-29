"""Smoke tests verifying the project scaffold is correctly installed."""
import types


def test_voyageur_package_importable() -> None:
    """voyageur package and all subpackages are importable after poetry install."""
    import voyageur
    import voyageur.cartography
    import voyageur.cli
    import voyageur.output
    import voyageur.routing
    import voyageur.tidal

    assert isinstance(voyageur, types.ModuleType)
    assert isinstance(voyageur.cli, types.ModuleType)
    assert isinstance(voyageur.routing, types.ModuleType)
    assert isinstance(voyageur.tidal, types.ModuleType)
    assert isinstance(voyageur.cartography, types.ModuleType)
    assert isinstance(voyageur.output, types.ModuleType)


def test_cli_main_importable() -> None:
    """voyageur.cli.main exposes a Typer app named 'app'."""
    import typer

    from voyageur.cli import main

    assert isinstance(main.app, typer.Typer)


def test_cli_help_output() -> None:
    """The CLI --help exits 0 and mentions voyageur."""
    from typer.testing import CliRunner

    from voyageur.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--from" in result.output
    assert "--to" in result.output
