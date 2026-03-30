# Story 4.3: Optimal Departure Time Suggestion

Status: ready-for-dev

## Story

As JC,
I want the system to suggest the optimal departure time window for a given passage,
so that tidal currents work in my favour and I can save significant time without manually iterating departure times.

## Acceptance Criteria

1. Given a passage request with `--optimize-departure` flag and `--window START/END` (ISO 8601 format: `2026-03-29T06:00/2026-03-29T12:00`), when the command runs, then the system evaluates departure times across the window at 30-minute intervals
2. The system returns the departure time that minimizes total passage duration
3. The output explains the recommendation: e.g. `Optimal departure: 06:30 — saving 00:45 vs 08:00 (your planned departure)`; if no improvement: `Optimal departure: 06:30 — no improvement vs 08:00`
4. `--depart` remains required and serves as the baseline for comparison in the output
5. `--window` is required when `--optimize-departure` is set; if absent, print `✗ --window required with --optimize-departure` to stderr and exit 1
6. If `window_end <= window_start` print `✗ --window end must be after start` to stderr and exit 1
7. The optimal route timeline is printed to stdout after the recommendation line
8. `tests/test_routing.py` passes: an optimal departure test over a 6-hour window with a tidal provider that favours early departures returns a departure time earlier than a mid-window baseline; `poetry run ruff check voyageur/ tests/` returns zero violations

## Tasks / Subtasks

- [ ] Créer `voyageur/routing/departure.py` — `DepartureResult` + `OptimalDeparturePlanner` (AC: 1, 2)
  - [ ] Dataclass `DepartureResult(optimal_departure, optimal_route, baseline_departure, baseline_route, time_saved)`
  - [ ] Classe `OptimalDeparturePlanner(tidal: TidalProvider, cartography: CartographyProvider)`
  - [ ] Méthode `scan(origin, destination, window_start, window_end, wind, boat, scan_interval_minutes=30, step_minutes=15) -> DepartureResult`
  - [ ] Boucle : `t = window_start`; incrémenter par `scan_interval_minutes` jusqu'à `t <= window_end` ; au moins une évaluation (window_start) même si fenêtre = 0
  - [ ] Utiliser `IsochroneRoutePlanner` pour chaque `t`
  - [ ] Sélectionner `t` minimisant `route.total_duration`
  - [ ] `baseline_departure` = `departure_time` fourni par le caller (--depart) ; `baseline_route` = route pour ce temps
  - [ ] `time_saved` = `baseline_route.total_duration - optimal_route.total_duration` (peut être négative/zéro)

- [ ] Modifier `voyageur/cli/main.py` — ajouter `--optimize-departure` + `--window` (AC: 3, 4, 5, 6, 7)
  - [ ] Ajouter `optimize_departure: bool = typer.Option(False, "--optimize-departure", is_flag=True, help="Find optimal departure in window")`
  - [ ] Ajouter `window: str | None = typer.Option(None, "--window", help="Search window ISO/ISO (e.g. 2026-03-29T06:00/2026-03-29T12:00)")`
  - [ ] Après validation existante : si `optimize_departure` et `window is None` → erreur stderr + Exit(1)
  - [ ] Parser la fenêtre : splitter sur `/`, parser chaque partie avec `_parse_depart()`, valider `window_end > window_start`
  - [ ] Dans le bloc d'imports lazy : ajouter `from voyageur.routing.departure import OptimalDeparturePlanner`
  - [ ] Branche `optimize_departure` : appeler `OptimalDeparturePlanner(tidal, cartography).scan(...)` avec `baseline_departure=departure_time`
  - [ ] Formatter la ligne de recommandation + la timeline de la route optimale (via `format_timeline`)

- [ ] Modifier `tests/test_routing.py` — nouveaux tests (AC: 8)
  - [ ] Définir `_EarlyFavorableTidalProvider` localement (retourne `TidalState(current_direction=180.0, current_speed=2.0, ...)` si `at.hour < 7`, sinon zéro)
  - [ ] `test_optimal_departure_6h_window_returns_earlier_departure` : fenêtre 06:00–12:00, baseline=08:00 → vérifier `result.optimal_departure.hour < 8`
  - [ ] `test_optimal_departure_result_contains_route` : vérifier `isinstance(result.optimal_route, Route)` et `len(result.optimal_route.waypoints) >= 1`

- [ ] Valider (AC: 8)
  - [ ] `poetry run ruff check voyageur/ tests/`
  - [ ] `poetry run pytest tests/ -v`

## Dev Notes

### 1. Nouveau fichier : `voyageur/routing/departure.py`

```python
import dataclasses
import datetime

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import BoatProfile, Route, WindCondition
from voyageur.routing.isochrone import IsochroneRoutePlanner
from voyageur.tidal.protocol import TidalProvider


@dataclasses.dataclass
class DepartureResult:
    optimal_departure: datetime.datetime
    optimal_route: Route
    baseline_departure: datetime.datetime
    baseline_route: Route
    time_saved: datetime.timedelta


class OptimalDeparturePlanner:
    """Scans a departure window and returns the time with shortest passage duration."""

    def __init__(self, tidal: TidalProvider, cartography: CartographyProvider) -> None:
        self._tidal = tidal
        self._cartography = cartography

    def scan(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        window_start: datetime.datetime,
        window_end: datetime.datetime,
        baseline_departure: datetime.datetime,
        wind: WindCondition,
        boat: BoatProfile,
        scan_interval_minutes: int = 30,
        step_minutes: int = 15,
    ) -> DepartureResult:
        planner = IsochroneRoutePlanner(self._tidal, self._cartography)
        step = datetime.timedelta(minutes=scan_interval_minutes)

        best_t = window_start
        best_route = planner.compute(
            origin=origin, destination=destination, departure_time=window_start,
            wind=wind, boat=boat, step_minutes=step_minutes,
        )

        t = window_start + step
        while t <= window_end:
            route = planner.compute(
                origin=origin, destination=destination, departure_time=t,
                wind=wind, boat=boat, step_minutes=step_minutes,
            )
            if route.total_duration < best_route.total_duration:
                best_t = t
                best_route = route
            t += step

        baseline_route = planner.compute(
            origin=origin, destination=destination, departure_time=baseline_departure,
            wind=wind, boat=boat, step_minutes=step_minutes,
        )
        time_saved = baseline_route.total_duration - best_route.total_duration

        return DepartureResult(
            optimal_departure=best_t,
            optimal_route=best_route,
            baseline_departure=baseline_departure,
            baseline_route=baseline_route,
            time_saved=time_saved,
        )
```

> **Important** : `DepartureResult` est défini dans `departure.py`, PAS dans `models.py` — c'est un type interne au module routing.

### 2. Parsing de la fenêtre `--window` dans `cli/main.py`

Ajouter une fonction locale (ou inliner dans `plan()`) :

```python
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
```

Réutilise `_parse_depart()` déjà présent dans `main.py` — ne pas dupliquer la logique ISO.

### 3. Nouvelles options Typer dans `plan()`

```python
optimize_departure: bool = typer.Option(
    False, "--optimize-departure", is_flag=True,
    help="Find optimal departure time in --window",
),
window: str | None = typer.Option(
    None, "--window",
    help="Search window ISO/ISO (e.g. 2026-03-29T06:00/2026-03-29T12:00)",
),
```

Placer après les options existantes, avant la fermeture `) -> None:`.

### 4. Bloc de validation `--optimize-departure` dans `plan()` (après les validations existantes)

```python
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
```

### 5. Branche `optimize_departure` dans le bloc d'imports lazy + exécution

```python
from voyageur.routing.departure import OptimalDeparturePlanner
```

(Ajout à la liste des imports lazy déjà présents dans `plan()`.)

```python
if optimize_departure and window_range is not None:
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
    opt_hhmm = result.optimal_departure.strftime("%H:%M")
    base_hhmm = result.baseline_departure.strftime("%H:%M")
    saved = result.time_saved
    saved_str = f"{int(saved.total_seconds() // 3600):02d}:{int((saved.total_seconds() % 3600) // 60):02d}"
    if saved.total_seconds() > 0:
        rec_line = f"Optimal departure: {opt_hhmm} — saving {saved_str} vs {base_hhmm}"
    else:
        rec_line = f"Optimal departure: {opt_hhmm} — no improvement vs {base_hhmm}"
    typer.echo(rec_line)
    typer.echo(format_timeline(result.optimal_route, wind=wind_condition))
```

> **Priorité** : cette branche est exclusive — si `optimize_departure` est True, ne pas entrer dans les branches `criteria_list` ou single-route.

### 6. Ordre des branches dans `plan()` (après imports lazy)

```
if optimize_departure:
    # branche 4.3
elif criteria_list is not None:
    # branche 4.2
else:
    # branche single-route (2.2 / 4.1)
```

### 7. Formatter le `time_saved` — cas négatif

Si `time_saved` est négatif (le baseline est meilleur), afficher `"no improvement"` sans la valeur négative. La formule `saved.total_seconds() > 0` couvre ce cas.

### 8. Test — `_EarlyFavorableTidalProvider`

Définir localement dans `test_routing.py` (ne pas polluer `conftest.py` avec un mock spécialisé) :

```python
class _EarlyFavorableTidalProvider:
    """Returns 2kn southbound current before 07:00 UTC, zero otherwise."""
    def get_current(self, lat: float, lon: float, at: datetime.datetime) -> TidalState:
        if at.hour < 7:
            return TidalState(
                timestamp=at, current_direction=180.0, current_speed=2.0, water_height=0.0,
            )
        return TidalState(
            timestamp=at, current_direction=0.0, current_speed=0.0, water_height=0.0,
        )
```

Scénario : fenêtre 06:00–12:00, baseline 08:00, vent 240°/15kn, Cherbourg→Granville.
- Départ 06:00 : courant 2kn sud favorable → durée courte
- Départ 08:00 (baseline) : courant nul → durée standard
- Attendu : `result.optimal_departure.hour < 8`

```python
def test_optimal_departure_6h_window_returns_earlier_departure(
    mock_cartography, boat
):
    """Optimal departure avec courant favorable avant 07:00 doit être avant 08:00."""
    UTC = datetime.timezone.utc
    window_start = datetime.datetime(2026, 3, 29, 6, 0, tzinfo=UTC)
    window_end = datetime.datetime(2026, 3, 29, 12, 0, tzinfo=UTC)
    baseline = datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)
    wind = WindCondition(timestamp=window_start, direction=240.0, speed=15.0)
    planner = OptimalDeparturePlanner(
        tidal=_EarlyFavorableTidalProvider(), cartography=mock_cartography
    )
    result = planner.scan(
        origin=CHERBOURG,
        destination=GRANVILLE,
        window_start=window_start,
        window_end=window_end,
        baseline_departure=baseline,
        wind=wind,
        boat=boat,
        scan_interval_minutes=30,
    )
    assert result.optimal_departure.hour < 8
    assert result.time_saved.total_seconds() > 0
```

### 9. Import additionnel dans `tests/test_routing.py`

```python
from voyageur.models import TidalState  # déjà importé via conftest, mais explicite ici
from voyageur.routing.departure import DepartureResult, OptimalDeparturePlanner
```

### 10. Ordre lon/lat (rappel critique)

Aucun appel direct à `_GEOD` dans `departure.py` — délégué à `IsochroneRoutePlanner`. Pas de risque d'inversion lon/lat dans ce module.

### 11. Fichiers à modifier/créer

| Action | Fichier |
|--------|---------|
| Créer | `voyageur/routing/departure.py` |
| Modifier | `voyageur/cli/main.py` — `--optimize-departure`, `--window`, branche optimize, `_parse_window()` |
| Modifier | `tests/test_routing.py` — `_EarlyFavorableTidalProvider` + 2 nouveaux tests |

### 12. Fichiers à NE PAS toucher

- `voyageur/models.py` — `DepartureResult` va dans `departure.py`
- `voyageur/routing/isochrone.py` — utilisé en boîte noire
- `voyageur/routing/multi.py` — non concerné
- `voyageur/routing/planner.py` — non concerné
- `voyageur/output/formatter.py` — `format_timeline()` utilisé tel quel
- `tests/conftest.py` — ne pas y ajouter de mock spécialisé story 4.3

### 13. Apprentissages stories précédentes

**Story 4.2 (multi-critères) :**
- Imports lazy dans `plan()` : ajouter à la liste des imports lazy dans le corps de `plan()`
- Patron `if/elif/else` pour les branches CLI : maintenir l'ordre `optimize_departure → criteria_list → single`
- Ruff ligne ≤ 88 chars — surveiller la ligne `f"✗ Invalid --window format: {window!r}."` + continuation

**Story 4.1 (isochrone) :**
- `IsochroneRoutePlanner` signature complète : `compute(origin, destination, departure_time, wind, boat, step_minutes=15)`
- `route.total_duration` est un `datetime.timedelta` — comparaison directe via `<` fonctionne

**Story 2.4 (CLI) :**
- `typer.Option(False, "--flag", is_flag=True)` pour les flags booléens
- Tous les messages d'erreur via `typer.echo(..., err=True)` + `raise typer.Exit(1)`

### References

- `voyageur/routing/isochrone.py` — `IsochroneRoutePlanner` (boîte noire à réutiliser)
- `voyageur/cli/main.py` — `_parse_depart()` à réutiliser dans `_parse_window()`; structure `plan()` et imports lazy
- `voyageur/output/formatter.py` — `format_timeline()` pour afficher la route optimale
- `_bmad-output/planning-artifacts/epics.md` — Story 4.3 ACs
- `_bmad-output/implementation-artifacts/4-2-multi-criteria-route-computation.md` — notes CLI pattern

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
