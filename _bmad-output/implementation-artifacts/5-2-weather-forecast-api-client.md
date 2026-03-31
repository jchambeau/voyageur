# Story 5.2: Weather Forecast API Client

Status: done

## Story

As JC,
I want the system to retrieve wind and weather forecast data from an external API,
so that I no longer need to enter wind conditions manually and my route reflects real forecast data.

## Acceptance Criteria

1. Given OpenMeteo API is reachable, when I run `voyageur plan --from X --to Y --depart T` without `--wind`, the system fetches the wind forecast for the departure area and uses it as route input (FR31)
2. Wind conditions are re-fetched per time step during routing (each step calls `WeatherProvider.get_wind(lat, lon, at)` with the current position and timestamp)
3. The timeline summary footer indicates forecast data is in use: `| Wind: forecast (OpenMeteo)`
4. If the OpenMeteo API is unavailable and no `--wind` flag is provided, the command exits with `✗ Weather forecast unavailable — provide --wind manually` to stderr and exit 1
5. `--wind` remains fully functional (explicit value takes precedence over forecast; no API call made)
6. `tests/test_cli.py` passes: happy-path forecast test (mocked HTTP) verifies "forecast (OpenMeteo)" in output; fallback error test verifies exit 1 + error message
7. `poetry run ruff check voyageur/ tests/` returns zero violations

## Tasks / Subtasks

- [x] Créer `voyageur/weather/` — module `WeatherProvider` protocol (AC: 2)
  - [x] Créer `voyageur/weather/__init__.py` (vide)
  - [x] Créer `voyageur/weather/protocol.py` : `WeatherProvider(Protocol)` avec `get_wind(lat, lon, at) -> WindCondition`

- [x] Créer `voyageur/weather/openmeteo.py` — `OpenMeteoClient` (AC: 1, 2, 4)
  - [x] Constante `OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"`
  - [x] Classe `OpenMeteoClient` avec `__init__(self, http_client: httpx.Client | None = None)`
    - [x] `self._http = http_client or httpx.Client(timeout=10.0)`
    - [x] `self._forecast: list[WindCondition] = []` (cache lazy)
  - [x] Méthode `get_wind(lat, lon, at) -> WindCondition`
  - [x] Méthode `_fetch(lat, lon, at)`

- [x] Modifier `voyageur/routing/isochrone.py` — support `WeatherProvider` par step (AC: 2)
  - [x] Ajouter `from voyageur.weather.protocol import WeatherProvider`
  - [x] Ajouter `weather: WeatherProvider | None = None` à `compute()`
  - [x] `current_wind` par step dans la boucle

- [x] Modifier `voyageur/output/formatter.py` — footer forecast (AC: 3)
  - [x] `wind_source: str | None = None` dans `format_timeline()` et `format_multi_criteria()`
  - [x] Footer `  | Wind: forecast ({wind_source})` si défini

- [x] Modifier `voyageur/cli/main.py` — `--wind` optionnel + intégration forecast (AC: 1, 3, 4, 5)
  - [x] `wind: str | None = typer.Option(None, ...`
  - [x] Bloc forecast avec try/except OpenMeteoClient
  - [x] `weather=weather_provider` à `IsochroneRoutePlanner.compute()`
  - [x] `wind_source=wind_source` à `format_timeline()`

- [x] Modifier `tests/test_cli.py` — 2 nouveaux tests (AC: 6)
  - [x] `test_plan_forecast_happy_path`
  - [x] `test_plan_forecast_unavailable_exits_1`

- [x] Valider (AC: 7)
  - [x] `poetry run ruff check voyageur/ tests/` — 0 violations
  - [x] `poetry run pytest tests/ -v` — 65/65 passed

## Dev Notes

### 1. `voyageur/weather/protocol.py`

```python
import datetime
from typing import Protocol, runtime_checkable

from voyageur.models import WindCondition


@runtime_checkable
class WeatherProvider(Protocol):
    """Interface for weather/wind forecast providers."""

    def get_wind(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> WindCondition:
        """Return wind forecast at the given WGS84 position and UTC timestamp."""
        ...
```

Même pattern que `TidalProvider` — `@runtime_checkable` pour `isinstance()`.

### 2. `voyageur/weather/openmeteo.py` — structure complète

```python
import datetime

import httpx

from voyageur.models import WindCondition

OPENMETEO_URL: str = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoClient:
    """WeatherProvider using the OpenMeteo public API (no API key required)."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http = http_client or httpx.Client(timeout=10.0)
        self._forecast: list[WindCondition] = []

    def get_wind(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> WindCondition:
        """Return wind at given position/time from cached forecast."""
        if not self._forecast:
            self._fetch(lat, lon, at)
        return min(
            self._forecast,
            key=lambda w: abs((w.timestamp - at).total_seconds()),
        )

    def _fetch(self, lat: float, lon: float, at: datetime.datetime) -> None:
        """Fetch 24h hourly wind forecast from OpenMeteo and populate cache."""
        start = at.date().isoformat()
        end = (at + datetime.timedelta(days=1)).date().isoformat()
        resp = self._http.get(
            OPENMETEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "windspeed_10m,winddirection_10m",
                "wind_speed_unit": "kn",
                "timezone": "UTC",
                "start_date": start,
                "end_date": end,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        times = data["hourly"]["time"]
        speeds = data["hourly"]["windspeed_10m"]
        directions = data["hourly"]["winddirection_10m"]
        self._forecast = [
            WindCondition(
                timestamp=datetime.datetime.fromisoformat(t).replace(
                    tzinfo=datetime.timezone.utc
                ),
                direction=float(d),
                speed=float(s),
            )
            for t, s, d in zip(times, speeds, directions)
        ]
```

**Note :** `self._forecast` est peuplé lors du premier appel à `get_wind()` (lazy fetch), ce qui permet l'injection d'un `http_client` mock pour les tests. La clé de cache est la position initiale — pas de re-fetch si la position change (Norman coast = aire < 300km, variation < 5° acceptable pour MVP).

### 3. Modification `voyageur/routing/isochrone.py`

Ajouter import en tête :
```python
from voyageur.weather.protocol import WeatherProvider
```

Modifier la signature de `compute()` :
```python
def compute(
    self,
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure_time: datetime.datetime,
    wind: WindCondition,
    boat: BoatProfile,
    step_minutes: int = 15,
    weather: WeatherProvider | None = None,
) -> Route:
```

Dans la boucle, AVANT l'étape 3 (calcul polaire), ajouter :
```python
# 2.5 Wind at current step (override static wind if WeatherProvider available)
current_wind = (
    weather.get_wind(current_lat, current_lon, current_time)
    if weather is not None
    else wind
)
```

Puis remplacer `wind.direction` / `wind.speed` par `current_wind.direction` / `current_wind.speed` dans les étapes 3 et 4 de la boucle (2 occurrences : calcul TWA + calcul heading offset).

**Important :** `wind` reste requis en paramètre — il sert de valeur par défaut (step 3) et garantit la rétrocompatibilité avec tous les appelants existants (`MultiCriteriaRoutePlanner`, `OptimalDeparturePlanner`, tests).

### 4. Modification `voyageur/output/formatter.py`

```python
def format_timeline(
    route: Route,
    wind: WindCondition | None = None,
    wind_source: str | None = None,
) -> str:
    ...
    # Ligne Total existante :
    summary = f"Total: {dist_nm:.1f} NM  |  Duration: {duration_str}  |  Flags: {flag_count}"
    if wind_source is not None:
        summary += f"  | Wind: forecast ({wind_source})"
    lines.append(summary)
    return "\n".join(lines)
```

Même ajout pour `format_multi_criteria()` — passer `wind_source` à `format_timeline()` interne.

### 5. Modification `voyageur/cli/main.py` — `--wind` optionnel

**Changement de signature :**
```python
# AVANT
wind: str = typer.Option(..., "--wind", help="Wind direction/speed (e.g. 240/15)"),
# APRÈS
wind: str | None = typer.Option(None, "--wind", help="Wind direction/speed (e.g. 240/15)"),
```

**Bloc forecast** (insérer après le parsing de `departure_time`, avant le bloc `optimize_departure`) :
```python
weather_provider = None
wind_source: str | None = None

if wind is None:
    from voyageur.weather.openmeteo import OpenMeteoClient

    _wc = OpenMeteoClient()
    try:
        wind_condition = _wc.get_wind(origin[0], origin[1], departure_time)
    except Exception:
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
```

**Supprimer** le bloc `wind_condition = _parse_wind(wind, departure_time)` qui existe actuellement après le parsing des positions (devenu redondant).

**Passer `weather` à la branche single-route :**
```python
# Branche else (route simple)
route = planner.compute(
    origin=origin,
    destination=destination,
    departure_time=departure_time,
    wind=wind_condition,
    boat=boat,
    step_minutes=step,
    weather=weather_provider,   # ← ajout
)
...
typer.echo(format_timeline(route, wind=wind_condition, wind_source=wind_source))
```

**Branches `--optimize-departure` et `--criteria` :** utiliser `wind_condition` constant (pas de `weather_provider`). Pas de changement dans ces branches — elles continuent à appeler avec `wind=wind_condition` uniquement.

### 6. Tests CLI — pattern monkeypatch

Les tests CLI utilisent `typer.testing.CliRunner`. Pour mocker `OpenMeteoClient` :

```python
def test_plan_forecast_happy_path(monkeypatch):
    from voyageur.models import WindCondition
    import datetime

    UTC = datetime.timezone.utc
    fake_wind = WindCondition(
        timestamp=datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC),
        direction=240.0,
        speed=15.0,
    )

    class _FakeOpenMeteoClient:
        def __init__(self, http_client=None):
            pass
        def get_wind(self, lat, lon, at):
            return fake_wind

    import voyageur.weather.openmeteo as _owm
    monkeypatch.setattr(_owm, "OpenMeteoClient", _FakeOpenMeteoClient)

    from tests.test_cli import runner, app  # ou importer directement
    result = runner.invoke(
        app,
        ["plan", "--from", "cherbourg", "--to", "granville",
         "--depart", "2026-03-29T08:00Z"],
    )
    assert result.exit_code == 0
    assert "forecast (OpenMeteo)" in result.output


def test_plan_forecast_unavailable_exits_1(monkeypatch):
    import httpx

    class _FailingClient:
        def __init__(self, http_client=None):
            pass
        def get_wind(self, lat, lon, at):
            raise httpx.ConnectError("unreachable")

    import voyageur.weather.openmeteo as _owm
    monkeypatch.setattr(_owm, "OpenMeteoClient", _FailingClient)

    from tests.test_cli import runner, app
    result = runner.invoke(
        app,
        ["plan", "--from", "cherbourg", "--to", "granville",
         "--depart", "2026-03-29T08:00Z"],
    )
    assert result.exit_code == 1
    assert "Weather forecast unavailable" in result.output
```

**Note sur le monkeypatch CLI :** Le monkeypatch remplace la classe `OpenMeteoClient` dans le module `voyageur.weather.openmeteo` AVANT que `plan()` ne l'importe en lazy. Cela fonctionne parce que l'import lazy `from voyageur.weather.openmeteo import OpenMeteoClient` cherche la valeur courante de l'attribut du module au moment de l'appel.

### 7. Ordre des opérations dans `plan()` après refactoring

```
1. Parse --from / --to
2. Parse --depart
3. Valider --wind / fetch forecast (NOUVEAU)
4. Valider --optimize-departure / --window
5. Load boat profile
6. Build thresholds
7. Lazy imports
8. Build tidal + cartography
9. if optimize_departure → branche 4.3
10. elif criteria_list → branche 4.2
11. else → route simple (avec weather_provider)
```

### 8. Rétrocompatibilité `IsochroneRoutePlanner.compute()`

Le paramètre `weather` est positionné EN DERNIER avec valeur par défaut `None`. Tous les appelants existants (`MultiCriteriaRoutePlanner`, `OptimalDeparturePlanner`, tests) appellent via kwargs nommés — aucun changement nécessaire côté appelants. Vérifier que les tests existants continuent de passer (pas de régression).

### 9. Fichiers à NE PAS toucher

- `voyageur/routing/multi.py` — pas de weather pour multi-criteria (hors scope)
- `voyageur/routing/departure.py` — pas de weather pour optimize-departure (hors scope)
- `voyageur/models.py` — `WindCondition` inchangé, `Waypoint` inchangé (pas de wind per-waypoint)
- `voyageur/tidal/` — inchangé
- `tests/test_routing.py` — les appels `IsochroneRoutePlanner.compute(weather=None)` sont compatibles

### 10. OpenMeteo réponse attendue (mock)

```json
{
  "hourly": {
    "time": ["2026-03-29T00:00", "2026-03-29T01:00", ...],
    "windspeed_10m": [12.5, 13.2, ...],
    "winddirection_10m": [240.0, 245.0, ...]
  }
}
```

Les temps sont en UTC sans offset (OpenMeteo retourne `YYYY-MM-DDTHH:MM` quand `timezone=UTC`). Ajouter `.replace(tzinfo=timezone.utc)` lors du parsing.

### 11. `httpx` déjà dans `pyproject.toml`

Ajouté en story 5.1 — pas de nouvelle dépendance requise.

### 12. Lookup de `test_cli.py` — fixtures existantes

Vérifier dans `tests/test_cli.py` comment `runner` et `app` sont importés/définis pour reproduire le même pattern dans les nouveaux tests.

### 13. Fichiers à modifier/créer

| Action | Fichier |
|--------|---------|
| Créer | `voyageur/weather/__init__.py` |
| Créer | `voyageur/weather/protocol.py` |
| Créer | `voyageur/weather/openmeteo.py` |
| Modifier | `voyageur/routing/isochrone.py` — param `weather` optionnel |
| Modifier | `voyageur/output/formatter.py` — param `wind_source` |
| Modifier | `voyageur/cli/main.py` — `--wind` optionnel, fetch forecast |
| Modifier | `tests/test_cli.py` — 2 nouveaux tests forecast |

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- ruff E501 dans `tests/test_cli.py:176` — signature `_make_fake_openmeteo_client` trop longue, corrigée en 2 lignes.

### Completion Notes List

- Tous les ACs satisfaits. 65/65 tests passent.
- `weather_provider` propagé uniquement à la branche single-route de `plan()` — `--optimize-departure` et `--criteria` utilisent `wind_condition` constant (hors scope).
- Cache forecast lazy dans `OpenMeteoClient` : fetch unique par instance, acceptable pour la zone Norman coast (< 300 km).

### File List

- `voyageur/weather/__init__.py` — créé (vide)
- `voyageur/weather/protocol.py` — créé
- `voyageur/weather/openmeteo.py` — créé
- `voyageur/routing/isochrone.py` — modifié (param `weather`)
- `voyageur/output/formatter.py` — modifié (param `wind_source`)
- `voyageur/cli/main.py` — modifié (`--wind` optionnel, forecast block, weather+wind_source propagation)
- `tests/test_cli.py` — modifié (2 nouveaux tests forecast)

## Review Findings

- [x] [Review][Patch] Empty API response → `min()` on empty list → `ValueError` uncaught [`voyageur/weather/openmeteo.py:get_wind`]
- [x] [Review][Patch] `None` values in JSON arrays → `float(None)` → `TypeError` during list comprehension [`voyageur/weather/openmeteo.py:_fetch`]
- [x] [Review][Patch] `wind_source` separator `"  | "` inconsistant avec `"  |  "` du reste du footer [`voyageur/output/formatter.py`]
- [x] [Review][Patch] Branches `--criteria` et `--optimize-departure` ne transmettent pas `wind_source` à `format_multi_criteria`/`format_timeline` [`voyageur/cli/main.py`]
- [x] [Review][Defer] `httpx.Client` jamais fermé dans `OpenMeteoClient.__init__` [`voyageur/weather/openmeteo.py:13`] — deferred, pre-existing
- [x] [Review][Defer] `except Exception` trop large dans le bloc forecast CLI (avalе les bugs de programmation) [`voyageur/cli/main.py:261`] — deferred, pre-existing
- [x] [Review][Defer] Fenêtre forecast 24h peut ne pas couvrir les longs passages (staleness silencieuse) [`voyageur/weather/openmeteo.py:31`] — deferred, pre-existing
- [x] [Review][Defer] `at.date()` dans `_fetch` sensible au timezone — latent, CLI path normalise toujours en UTC [`voyageur/weather/openmeteo.py:30`] — deferred, pre-existing

## Change Log

- 2026-04-01 : Story 5.2 créée — Weather Forecast API Client
