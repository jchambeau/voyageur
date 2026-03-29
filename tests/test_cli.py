"""Tests for the CLI plan command — Story 2.4."""
import pytest
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
            "--from", "PortInconnu",
            "--to", "Granville",
            "--depart", UTC_ISO,
            "--wind", "240/15",
        ],
    )
    assert result.exit_code == 1
    assert "✗" in result.output
