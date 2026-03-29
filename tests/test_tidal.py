"""Tests for HarmonicTidalModel."""
import datetime

from voyageur.models import TidalState
from voyageur.tidal.impl import HarmonicTidalModel
from voyageur.tidal.protocol import TidalProvider

# Reference port coordinates
CHERBOURG = (49.6453, -1.6222)
LE_HAVRE = (49.4892, 0.1080)
SAINT_MALO = (48.6490, -1.9800)
MIDPOINT = (49.2, -0.8)   # between Cherbourg and Le Havre


def test_harmonic_tidal_model_satisfies_protocol() -> None:
    assert isinstance(HarmonicTidalModel(), TidalProvider)


def test_get_current_cherbourg(now: datetime.datetime) -> None:
    model = HarmonicTidalModel()
    result = model.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=now)
    assert isinstance(result, TidalState)
    assert result.timestamp == now
    assert result.current_speed > 0.0
    assert 0.0 <= result.current_direction < 360.0


def test_get_current_le_havre(now: datetime.datetime) -> None:
    model = HarmonicTidalModel()
    result = model.get_current(lat=LE_HAVRE[0], lon=LE_HAVRE[1], at=now)
    assert isinstance(result, TidalState)
    assert result.current_speed > 0.0
    assert 0.0 <= result.current_direction < 360.0


def test_get_current_saint_malo(now: datetime.datetime) -> None:
    model = HarmonicTidalModel()
    result = model.get_current(lat=SAINT_MALO[0], lon=SAINT_MALO[1], at=now)
    assert isinstance(result, TidalState)
    assert result.current_speed > 0.0
    assert 0.0 <= result.current_direction < 360.0


def test_current_reverses_over_half_m2_period(now: datetime.datetime) -> None:
    """Current direction should flip after ~6.21h (half the M2 period)."""
    model = HarmonicTidalModel()
    t0 = model.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=now)
    t_half = model.get_current(
        lat=CHERBOURG[0],
        lon=CHERBOURG[1],
        at=now + datetime.timedelta(hours=6.21),
    )
    # Circular difference in direction should be > 90° (expect ~180°)
    diff = abs(t0.current_direction - t_half.current_direction)
    diff = min(diff, 360.0 - diff)
    assert diff > 90.0


def test_current_speed_within_realistic_range(now: datetime.datetime) -> None:
    """All speeds over a 12h window must be within Norman coast range 0–5 kn."""
    model = HarmonicTidalModel()
    for i in range(25):
        at = now + datetime.timedelta(minutes=i * 30)
        result = model.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=at)
        assert 0.0 <= result.current_speed <= 5.0, (
            f"Speed {result.current_speed:.2f} kn out of range at step {i}"
        )


def test_interpolation_midpoint(now: datetime.datetime) -> None:
    """Intermediate position between ports returns valid TidalState."""
    model = HarmonicTidalModel()
    result = model.get_current(lat=MIDPOINT[0], lon=MIDPOINT[1], at=now)
    assert isinstance(result, TidalState)
    assert result.current_speed >= 0.0
    assert 0.0 <= result.current_direction < 360.0
