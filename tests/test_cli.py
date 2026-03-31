"""Tests for the CLI plan command — Story 2.4 & boat profile — Story 3.3."""
import datetime
import pathlib

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from voyageur.cli.main import app

UTC_ISO = "2026-03-29T08:00"


@pytest.fixture
def runner() -> CliRunner:
    """Typer CliRunner (stdout+stderr mixed in result.output)."""
    return CliRunner()


def test_plan_cherbourg_granville(runner: CliRunner) -> None:
    """Happy path: Cherbourg→Granville exits 0 and contains NM in output."""
    result = runner.invoke(
        app,
        [
            "plan",
            "--from", "Cherbourg",
            "--to", "Granville",
            "--depart", UTC_ISO,
            "--wind", "240/15",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NM" in result.output


def test_plan_invalid_port(runner: CliRunner) -> None:
    """Unknown port exits 1 and writes ✗ to stderr."""
    result = runner.invoke(
        app,
        [
            "plan",
            "--from", "PortInconnu",
            "--to", "Granville",
            "--depart", UTC_ISO,
            "--wind", "240/15",
        ],
    )
    assert result.exit_code == 1
    assert "✗" in result.output


# ---------------------------------------------------------------------------
# Boat profile management — Story 3.3
# ---------------------------------------------------------------------------


def test_config_create_saves_yaml(
    runner: CliRunner, tmp_path: pathlib.Path, monkeypatch
) -> None:
    """voyageur config --name ... saves a valid YAML file."""
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    result = runner.invoke(
        app,
        [
            "config",
            "--name", "TestBoat",
            "--loa", "10.0",
            "--draft", "1.5",
            "--sail-area", "50.0",
            "--default-step", "15",
        ],
    )
    assert result.exit_code == 0, result.output
    yaml_path = tmp_path / ".voyageur" / "boat.yaml"
    assert yaml_path.exists(), "boat.yaml not created"
    data = yaml.safe_load(yaml_path.read_text())
    assert data["name"] == "TestBoat"
    assert data["loa"] == pytest.approx(10.0)
    assert data["draft"] == pytest.approx(1.5)
    assert data["sail_area"] == pytest.approx(50.0)
    assert data["default_step"] == 15


def test_config_show_displays_profile(
    runner: CliRunner, tmp_path: pathlib.Path, monkeypatch
) -> None:
    """`voyageur config --show` displays saved profile on stdout."""
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    voyageur_dir = tmp_path / ".voyageur"
    voyageur_dir.mkdir()
    (voyageur_dir / "boat.yaml").write_text(
        "default_step: 15\ndraft: 1.8\nloa: 12.0\nname: MyBoat\nsail_area: 65.0\n"
    )
    result = runner.invoke(app, ["config", "--show"])
    assert result.exit_code == 0, result.output
    assert "MyBoat" in result.output
    assert "12.0" in result.output
    assert "1.8" in result.output
    assert "65.0" in result.output
    assert "15" in result.output


def test_config_show_missing_profile(
    runner: CliRunner, tmp_path: pathlib.Path, monkeypatch
) -> None:
    """`voyageur config --show` with no saved profile exits 1."""
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    result = runner.invoke(app, ["config", "--show"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# replan command — Story 4.4
# ---------------------------------------------------------------------------


def test_replan_happy_path(runner: CliRunner) -> None:
    """Happy path: replan Cherbourg→Granville exits 0 avec timeline."""
    result = runner.invoke(
        app,
        [
            "replan",
            "--from", "cherbourg",
            "--to", "granville",
            "--time", UTC_ISO,
            "--wind", "240/15",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NM" in result.output


def test_replan_changed_wind_differs_from_original(runner: CliRunner) -> None:
    """Deux replans avec vents différents produisent des outputs distincts."""
    result1 = runner.invoke(
        app,
        ["replan", "--from", "cherbourg", "--to", "granville",
         "--time", UTC_ISO, "--wind", "240/15"],
    )
    result2 = runner.invoke(
        app,
        ["replan", "--from", "cherbourg", "--to", "granville",
         "--time", UTC_ISO, "--wind", "0/20"],
    )
    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert result1.output != result2.output


def test_replan_invalid_port_exits_1(runner: CliRunner) -> None:
    """Port inconnu → exit 1 avec ✗."""
    result = runner.invoke(
        app,
        [
            "replan",
            "--from", "PortInconnu",
            "--to", "granville",
            "--time", UTC_ISO,
            "--wind", "240/15",
        ],
    )
    assert result.exit_code == 1
    assert "✗" in result.output


# ---------------------------------------------------------------------------
# Weather forecast — Story 5.2
# ---------------------------------------------------------------------------

UTC = datetime.timezone.utc
_FAKE_WIND_DIRECTION = 240.0
_FAKE_WIND_SPEED = 15.0


def _make_fake_openmeteo_client(
    direction: float = _FAKE_WIND_DIRECTION, speed: float = _FAKE_WIND_SPEED
):
    """Return a fake OpenMeteoClient class for monkeypatching."""
    from voyageur.models import WindCondition

    class _FakeOpenMeteoClient:
        def __init__(self, http_client=None) -> None:
            pass

        def get_wind(
            self, lat: float, lon: float, at: datetime.datetime
        ) -> WindCondition:
            return WindCondition(timestamp=at, direction=direction, speed=speed)

    return _FakeOpenMeteoClient


def test_plan_forecast_happy_path(runner: CliRunner, monkeypatch) -> None:
    """plan without --wind fetches forecast; output contains 'forecast (OpenMeteo)'."""
    import voyageur.weather.openmeteo as _owm

    monkeypatch.setattr(_owm, "OpenMeteoClient", _make_fake_openmeteo_client())
    result = runner.invoke(
        app,
        [
            "plan",
            "--from", "cherbourg",
            "--to", "granville",
            "--depart", UTC_ISO,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "forecast (OpenMeteo)" in result.output


def test_plan_forecast_unavailable_exits_1(runner: CliRunner, monkeypatch) -> None:
    """plan without --wind exits 1 with error message when API unavailable."""
    import voyageur.weather.openmeteo as _owm

    class _FailingClient:
        def __init__(self, http_client=None) -> None:
            pass

        def get_wind(self, lat: float, lon: float, at: datetime.datetime):
            raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(_owm, "OpenMeteoClient", _FailingClient)
    result = runner.invoke(
        app,
        [
            "plan",
            "--from", "cherbourg",
            "--to", "granville",
            "--depart", UTC_ISO,
        ],
    )
    assert result.exit_code == 1
    assert "Weather forecast unavailable" in result.output


def test_plan_draft_override(
    runner: CliRunner, tmp_path: pathlib.Path, monkeypatch
) -> None:
    """`voyageur plan --draft 2.1` overrides saved boat draft and exits 0."""
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    voyageur_dir = tmp_path / ".voyageur"
    voyageur_dir.mkdir()
    (voyageur_dir / "boat.yaml").write_text(
        "default_step: 15\ndraft: 1.8\nloa: 12.0\nname: TestBoat\nsail_area: 65.0\n"
    )
    result = runner.invoke(
        app,
        [
            "plan",
            "--from", "Cherbourg",
            "--to", "Granville",
            "--depart", UTC_ISO,
            "--wind", "240/15",
            "--draft", "2.1",
        ],
    )
    assert result.exit_code == 0, result.output
    # Non-overridden fields (loa, sail_area, name) come from saved profile
    # — no "defaults" warning expected
    assert "defaults" not in result.output.lower()
