"""Unit tests for OpenMeteoClient — Story 5.2."""
import datetime

import httpx
import pytest

from voyageur.models import WindCondition
from voyageur.weather.openmeteo import OpenMeteoClient
from voyageur.weather.protocol import WeatherProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 3, 29, 8, 0)


def _make_openmeteo_json(
    hours: int = 24,
    base_speed: float = 15.0,
    base_dir: float = 240.0,
    start: datetime.datetime = _NOW,
    nulls_at: set[int] | None = None,
) -> dict:
    """Build a realistic OpenMeteo JSON response."""
    times, speeds, dirs = [], [], []
    for i in range(hours):
        t = start + datetime.timedelta(hours=i)
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        if nulls_at and i in nulls_at:
            speeds.append(None)
            dirs.append(None)
        else:
            speeds.append(base_speed + i * 0.1)
            dirs.append(base_dir)
    return {
        "hourly": {
            "time": times,
            "windspeed_10m": speeds,
            "winddirection_10m": dirs,
        }
    }


class _MockResponse:
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

    def get(self, url: str, **kwargs) -> _MockResponse:
        if self._raise is not None:
            raise self._raise
        return _MockResponse(self._data or {})


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_openmeteo_satisfies_protocol():
    """OpenMeteoClient must satisfy WeatherProvider protocol."""
    assert isinstance(OpenMeteoClient(http_client=_MockHttpClient()), WeatherProvider)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_get_wind_happy_path():
    """get_wind returns nearest WindCondition from cached forecast."""
    data = _make_openmeteo_json()
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    result = client.get_wind(49.0, -1.6, _NOW)
    assert isinstance(result, WindCondition)
    assert result.direction == 240.0
    assert result.speed == pytest.approx(15.0)


def test_get_wind_nearest_time():
    """get_wind selects the forecast entry closest to the requested time."""
    data = _make_openmeteo_json()
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    # Request at hour +3.4 → should return hour +3 entry (speed 15.3)
    at = _NOW + datetime.timedelta(hours=3, minutes=24)
    result = client.get_wind(49.0, -1.6, at)
    assert result.speed == pytest.approx(15.3)


def test_get_wind_aware_datetime():
    """get_wind works with timezone-aware datetime (normalised internally)."""
    data = _make_openmeteo_json()
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    aware_now = _NOW.replace(tzinfo=datetime.timezone.utc)
    result = client.get_wind(49.0, -1.6, aware_now)
    assert isinstance(result, WindCondition)
    assert result.speed == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Empty forecast
# ---------------------------------------------------------------------------


def test_empty_forecast_raises():
    """get_wind raises ValueError when API returns empty arrays."""
    data = {"hourly": {"time": [], "windspeed_10m": [], "winddirection_10m": []}}
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    with pytest.raises(ValueError, match="empty forecast"):
        client.get_wind(49.0, -1.6, _NOW)


# ---------------------------------------------------------------------------
# None filtering
# ---------------------------------------------------------------------------


def test_null_values_filtered():
    """Entries with None speed/direction are excluded from cache."""
    data = _make_openmeteo_json(hours=4, nulls_at={0, 2})
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    result = client.get_wind(49.0, -1.6, _NOW)
    # Hour 0 is null, so nearest valid is hour 1
    assert result.speed == pytest.approx(15.1)


def test_all_null_raises():
    """If all entries are None, raises ValueError (empty forecast)."""
    data = _make_openmeteo_json(hours=3, nulls_at={0, 1, 2})
    client = OpenMeteoClient(http_client=_MockHttpClient(response_data=data))
    with pytest.raises(ValueError, match="empty forecast"):
        client.get_wind(49.0, -1.6, _NOW)


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------


def test_connect_error_wrapped():
    """httpx.ConnectError is wrapped as ValueError."""
    client = OpenMeteoClient(
        http_client=_MockHttpClient(raise_error=httpx.ConnectError("refused"))
    )
    with pytest.raises(ValueError, match="OpenMeteo forecast unavailable"):
        client.get_wind(49.0, -1.6, _NOW)


def test_timeout_error_wrapped():
    """httpx.ReadTimeout is wrapped as ValueError."""
    client = OpenMeteoClient(
        http_client=_MockHttpClient(raise_error=httpx.ReadTimeout("timeout"))
    )
    with pytest.raises(ValueError, match="OpenMeteo forecast unavailable"):
        client.get_wind(49.0, -1.6, _NOW)


def test_missing_key_wrapped():
    """Missing 'hourly' key in response is wrapped as ValueError."""
    client = OpenMeteoClient(
        http_client=_MockHttpClient(response_data={"other": {}})
    )
    with pytest.raises(ValueError, match="OpenMeteo forecast unavailable"):
        client.get_wind(49.0, -1.6, _NOW)
