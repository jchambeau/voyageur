"""Tests for HarmonicTidalModel and ShomTidalClient."""
import datetime

from voyageur.models import TidalState
from voyageur.tidal.impl import HarmonicTidalModel
from voyageur.tidal.protocol import TidalProvider
from voyageur.tidal.shom_client import ShomTidalClient


class _MockHttpResponse:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._data


class _MockHttpClient:
    def __init__(
        self,
        response_data: dict | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self._data = response_data
        self._raise = raise_error

    def get(self, url: str, **kwargs) -> _MockHttpResponse:
        if self._raise is not None:
            raise self._raise
        return _MockHttpResponse(self._data or {})

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


# --- ShomTidalClient tests ---


def test_shom_client_satisfies_protocol() -> None:
    assert isinstance(ShomTidalClient("key"), TidalProvider)


def test_shom_client_happy_path(now: datetime.datetime) -> None:
    client = ShomTidalClient(
        api_key="test-key",
        http_client=_MockHttpClient(
            response_data={"direction": 180.0, "speed": 2.3, "height": 3.5}
        ),
    )
    result = client.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=now)
    assert isinstance(result, TidalState)
    assert result.current_direction == 180.0
    assert result.current_speed == 2.3
    assert result.water_height == 3.5
    assert result.timestamp == now


def test_shom_client_fallback_on_error(
    now: datetime.datetime, capsys: object
) -> None:
    import httpx

    client = ShomTidalClient(
        api_key="test-key",
        http_client=_MockHttpClient(
            raise_error=httpx.ConnectError("Connection refused")
        ),
    )
    result = client.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=now)
    assert isinstance(result, TidalState)
    assert result.current_speed >= 0.0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "⚠ SHOM API unavailable" in captured.err


def test_shom_client_fallback_on_http_status_error(
    now: datetime.datetime, capsys: object
) -> None:
    """Non-2xx response (raise_for_status path) triggers fallback."""
    import httpx

    class _ErrorResponse:
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "403 Forbidden",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(403),
            )

        def json(self) -> dict:
            return {}

    class _StatusErrorClient:
        def get(self, url: str, **kwargs) -> _ErrorResponse:
            return _ErrorResponse()

    client = ShomTidalClient(
        api_key="test-key",
        http_client=_StatusErrorClient(),
    )
    result = client.get_current(lat=CHERBOURG[0], lon=CHERBOURG[1], at=now)
    assert isinstance(result, TidalState)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "⚠ SHOM API unavailable" in captured.err
