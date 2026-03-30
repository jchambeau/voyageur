"""Tests for the CLI plan command — Story 2.4 & boat profile — Story 3.3."""
import pathlib

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
