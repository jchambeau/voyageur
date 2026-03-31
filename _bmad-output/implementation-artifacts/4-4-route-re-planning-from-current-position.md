# Story 4.4: Route Re-planning from Current Position

Status: done

## Story

As JC,
I want to re-plan my route from my current position with updated conditions,
so that if wind or sea state changes mid-passage I can immediately get new viable options.

## Acceptance Criteria

1. Given updated conditions (current position, time, new wind), when I run `voyageur replan --from CURRENT_POS --time NOW --wind NEW_WIND --to DESTINATION`, then the system computes a new route from the current position to the destination and displays the timeline (same format as `plan` command)
2. `--from` and `--to` accept port names or `latN/lonW` coordinates (same as `plan`)
3. `--time` accepts ISO 8601 datetime (same parsing as `--depart` in `plan`)
4. If the new route is viable, the timeline is printed to stdout and exit code is 0
5. If no viable route exists (all segments flagged by safety thresholds), a `✗` alert is printed to stderr, the system scans the next 12 hours at 1-hour intervals to find the first viable departure, and reports it as `⚠ Next viable departure: HH:MM UTC` (or `⚠ No viable route in next 12 hours` if none found)
6. `--criteria` is supported (same as `plan` — enables `MultiCriteriaRoutePlanner`); if absent, single `IsochroneRoutePlanner` route
7. `--step`, `--max-wind`, `--max-current`, `--draft` are supported (same semantics as `plan`)
8. `tests/test_cli.py` passes: a replan happy-path exits 0 and contains timeline output; a replan with changed wind produces output distinct from the original; an invalid port exits 1 with `✗`; `poetry run ruff check voyageur/ tests/` returns zero violations

## Tasks / Subtasks

- [x] Ajouter `@app.command("replan")` dans `voyageur/cli/main.py` (AC: 1, 2, 3, 4, 6, 7)
  - [x] Fonction `replan(from_port, to_port, current_time_str, wind, step, max_wind, max_current, draft, criteria) -> None`
  - [x] Réutiliser `_parse_position()`, `_parse_depart()`, `_parse_wind()`, `_load_boat()` déjà dans `main.py`
  - [x] Même validations que `plan` : position, time, step, wind, criteria
  - [x] Imports lazy identiques à `plan` + `from voyageur.routing.isochrone import IsochroneRoutePlanner`
  - [x] Si `criteria` défini → `MultiCriteriaRoutePlanner` + `format_multi_criteria`
  - [x] Sinon → `IsochroneRoutePlanner` + `format_timeline`
  - [x] `evaluate_route()` sur la/les routes calculées

- [x] Implémenter la détection de "next viable departure" (AC: 5)
  - [x] Fonction `_handle_no_viable(...)` module-level dans `main.py`
  - [x] Boucle `for h in range(1, 13)` : tester `current_time + timedelta(hours=h)`
  - [x] `evaluate_route()` sur chaque route sondée
  - [x] Affiche `⚠ Next viable departure: HH:MM UTC` ou `⚠ No viable route in next 12 hours`
  - [x] Appelée si `flag_count == len(route.waypoints)` (tous les waypoints flagués)

- [x] Modifier `tests/test_cli.py` (AC: 8)
  - [x] `test_replan_happy_path` : exit 0, "NM" dans output
  - [x] `test_replan_changed_wind_differs_from_original` : deux replans avec vents différents → outputs distincts
  - [x] `test_replan_invalid_port_exits_1` : exit 1, "✗" dans output

- [x] Valider (AC: 8)
  - [x] `poetry run ruff check voyageur/ tests/`
  - [x] `poetry run pytest tests/ -v`

### Review Findings

- [x] [Review][Patch] `replan` else-branch ne vérifie pas `intersects_land`, contrairement à `plan()` [voyageur/cli/main.py — replan() else-branch] — **Med** — une route replannifiée qui croise la terre est retournée sans avertissement ; ajouter le bloc `cartography.intersects_land(route.waypoints)` identique à `plan()`
- [x] [Review][Patch] `_handle_no_viable` crée un nouveau `IsochroneRoutePlanner` à chaque itération de boucle [voyageur/cli/main.py — _handle_no_viable()] — **Low** — 12 instanciations inutiles ; extraire l'instance avant `for h in range(1, 13)`

## Dev Notes

### 1. Ajout de `replan` dans `main.py`

```python
@app.command("replan")
def replan(
    from_port: str = typer.Option(..., "--from", help="Current position (port or lat/lon)"),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    current_time_str: str = typer.Option(..., "--time", help="Current time (ISO 8601)"),
    wind: str = typer.Option(..., "--wind", help="Wind direction/speed (e.g. 240/15)"),
    step: int = typer.Option(15, "--step", help="Time step in minutes (1,5,15,30,60)"),
    max_wind: float | None = typer.Option(None, "--max-wind", help="Max wind speed (kn)", min=0.0),
    max_current: float | None = typer.Option(
        None, "--max-current", help="Max tidal current speed (kn)", min=0.0
    ),
    draft: float | None = typer.Option(None, "--draft", help="Override boat draft (m)", min=0.0),
    criteria: str | None = typer.Option(
        None, "--criteria",
        help="Route criteria: fastest,comfort,shelter,traffic or all",
    ),
) -> None:
    """Re-plan a sailing passage from current position with updated conditions."""
```

> **Nommage du paramètre** : Typer utilise `--time` mais la variable Python s'appelle `current_time_str` pour éviter le conflit avec `datetime` dans le corps de la fonction. Alternative : `time_str`.

### 2. Corps de `replan()` — validations

Même structure que `plan()` :

```python
current_time = _parse_depart(current_time_str)
if current_time is None:
    typer.echo(f"✗ Invalid time: {current_time_str!r}", err=True)
    raise typer.Exit(1)

origin = _parse_position(from_port)
if origin is None:
    typer.echo(f"✗ Unknown port or invalid position: {from_port!r}", err=True)
    raise typer.Exit(1)

destination = _parse_position(to_port)
if destination is None:
    typer.echo(f"✗ Unknown port or invalid position: {to_port!r}", err=True)
    raise typer.Exit(1)

if step not in (1, 5, 15, 30, 60):
    typer.echo(f"✗ --step must be one of 1, 5, 15, 30, 60 (got {step})", err=True)
    raise typer.Exit(1)

wind_condition = _parse_wind(wind, current_time)
if wind_condition is None:
    typer.echo(
        f"✗ Invalid wind format: {wind!r}. Expected DIR/SPD (e.g. 240/15)", err=True
    )
    raise typer.Exit(1)

boat, loaded, boat_thresholds = _load_boat()
if draft is not None:
    boat = dataclasses.replace(boat, draft=draft)
if not loaded:
    typer.echo("⚠ No boat profile found at ~/.voyageur/boat.yaml — using defaults.", err=True)

thresholds = SafetyThresholds(
    max_wind_kn=(max_wind if max_wind is not None else boat_thresholds.get("max_wind_kn")),
    max_current_kn=(max_current if max_current is not None else boat_thresholds.get("max_current_kn")),
)
```

### 3. Parsing criteria — même logique que `plan()`

```python
criteria_list: list[str] | None = None
if criteria is not None:
    from voyageur.routing.multi import CRITERIA as _ALL_CRITERIA
    raw = (
        list(_ALL_CRITERIA) if criteria.strip() == "all"
        else [c.strip() for c in criteria.split(",")]
    )
    invalid = [c for c in raw if c not in _ALL_CRITERIA]
    if invalid:
        typer.echo(
            f"✗ Unknown criteria: {', '.join(invalid)}."
            f" Valid: {', '.join(_ALL_CRITERIA)}",
            err=True,
        )
        raise typer.Exit(1)
    if "traffic" in raw:
        typer.echo("⚠ traffic: no shipping lane data — falls back to fastest", err=True)
    criteria_list = raw
```

### 4. Imports lazy dans `replan()`

```python
from voyageur.cartography.impl import GeoJsonCartography
from voyageur.output.formatter import format_multi_criteria, format_timeline
from voyageur.routing.isochrone import IsochroneRoutePlanner
from voyageur.routing.multi import MultiCriteriaRoutePlanner
from voyageur.routing.safety import evaluate_route
from voyageur.tidal.impl import HarmonicTidalModel
```

Même liste que dans `plan()` — le pattern lazy s'applique de la même façon.

### 5. Branche multi-critères dans `replan()`

```python
cartography = GeoJsonCartography()
tidal = HarmonicTidalModel()

if criteria_list is not None:
    multi = MultiCriteriaRoutePlanner(tidal=tidal, cartography=cartography)
    results = multi.compute_all(
        origin=origin, destination=destination, departure_time=current_time,
        wind=wind_condition, boat=boat, step_minutes=step, criteria=criteria_list,
    )
    for route in results.values():
        evaluate_route(route, wind_condition, thresholds)
    first_route = next(iter(results.values()))
    if len(first_route.waypoints) > 0 and all(wp.flagged for wp in first_route.waypoints):
        _handle_no_viable(origin, destination, current_time, wind_condition, boat,
                          tidal, cartography, thresholds, step)
        raise typer.Exit(1)
    typer.echo(format_multi_criteria(results, wind=wind_condition))
else:
    route = IsochroneRoutePlanner(tidal=tidal, cartography=cartography).compute(
        origin=origin, destination=destination, departure_time=current_time,
        wind=wind_condition, boat=boat, step_minutes=step,
    )
    flag_count = evaluate_route(route, wind_condition, thresholds)
    if flag_count > 0 and flag_count == len(route.waypoints):
        _handle_no_viable(origin, destination, current_time, wind_condition, boat,
                          tidal, cartography, thresholds, step)
        raise typer.Exit(1)
    typer.echo(format_timeline(route, wind=wind_condition))
```

### 6. Fonction `_handle_no_viable()` (module-level dans `main.py`)

```python
def _handle_no_viable(
    origin: tuple[float, float],
    destination: tuple[float, float],
    current_time: datetime.datetime,
    wind: "WindCondition",
    boat: "BoatProfile",
    tidal: object,
    cartography: object,
    thresholds: "SafetyThresholds",
    step_minutes: int,
) -> None:
    """Print ✗ error and scan next 12h for viable departure."""
    from voyageur.routing.isochrone import IsochroneRoutePlanner
    from voyageur.routing.safety import evaluate_route

    typer.echo("✗ No viable conditions — all segments exceed safety thresholds.", err=True)
    for h in range(1, 13):
        t = current_time + datetime.timedelta(hours=h)
        route = IsochroneRoutePlanner(tidal, cartography).compute(
            origin=origin, destination=destination, departure_time=t,
            wind=wind, boat=boat, step_minutes=step_minutes,
        )
        fc = evaluate_route(route, wind, thresholds)
        if fc < len(route.waypoints):
            typer.echo(
                f"⚠ Next viable departure: {t.strftime('%H:%M')} UTC", err=True
            )
            return
    typer.echo("⚠ No viable route in next 12 hours", err=True)
```

> **Placement** : Définir `_handle_no_viable` AVANT les fonctions `plan()` et `replan()` dans `main.py`. Elle ne doit pas être à l'intérieur d'une autre fonction. Les type hints en `str` (quotes) évitent les imports circulaires au niveau module.

> **Alternative si `_handle_no_viable` alourdit `main.py`** : inliner la logique directement dans `replan()`. C'est acceptable si la fonction n'est appelée qu'une fois.

### 7. Tests dans `tests/test_cli.py`

Ajouter en bas du fichier :

```python
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
```

### 8. Remarque sur `plan()` et `_handle_no_viable()`

La logique "no viable" dans `plan()` reste inchangée (inline dans `plan()`). `_handle_no_viable()` est **uniquement pour `replan()`**. Ne pas remanier le code existant de `plan()`.

### 9. Ordre des commandes Typer dans `main.py`

```python
app = typer.Typer(...)
app.add_typer(config_app, name="config")  # existant

# Ajouter APRÈS la définition de app.add_typer(config_app, ...)
# mais les fonctions @app.command() peuvent être définies partout dans le fichier
```

`plan()` et `replan()` sont deux `@app.command()` indépendants. Typer les registre automatiquement. L'ordre de définition dans le fichier n'a pas d'importance fonctionnelle.

### 10. Ruff — points de vigilance

- `_handle_no_viable` : les type hints entre quotes (`"WindCondition"` etc.) évitent de devoir importer ces types au top-level. Ou utiliser `from __future__ import annotations` en haut du fichier — **mais vérifier que `main.py` ne l'utilise pas déjà avant d'ajouter**.
- Lignes ≤ 88 chars — surveiller les f-strings dans les messages d'erreur.
- Imports lazy : TOUS dans le corps de la fonction (pas au top-level).

### 11. `SafetyThresholds` — déjà importé

`from voyageur.models import BoatProfile, SafetyThresholds, WindCondition` est au top de `main.py` — pas besoin de re-importer.

### 12. Fichiers à modifier/créer

| Action | Fichier |
|--------|---------|
| Modifier | `voyageur/cli/main.py` — `@app.command("replan")` + `_handle_no_viable()` |
| Modifier | `tests/test_cli.py` — 3 nouveaux tests |

### 13. Fichiers à NE PAS toucher

- `voyageur/routing/isochrone.py` — utilisé en boîte noire
- `voyageur/routing/multi.py` — utilisé en boîte noire
- `voyageur/routing/departure.py` (story 4.3) — non requis pour 4.4
- `voyageur/models.py` — aucun nouveau modèle requis
- `voyageur/output/formatter.py` — `format_timeline()` et `format_multi_criteria()` réutilisés tels quels
- `voyageur/cli/config.py` — non concerné
- `tests/test_routing.py`, `tests/conftest.py` — ne pas modifier

### 14. Dépendance story 4.2

`replan` réutilise `MultiCriteriaRoutePlanner` et `format_multi_criteria` de story 4.2 — ces modules sont déjà disponibles (story 4.2 est `done`). Pas de nouveau code à écrire dans `multi.py` ou `formatter.py`.

### 15. Apprentissages stories précédentes

**Story 4.3 (optimal departure) :**
- `_parse_depart()` → retourne `datetime | None` ; même parsing pour `--time`
- Pattern lazy imports identique pour tous les modules routing

**Story 4.2 (multi-critères) :**
- `evaluate_route()` mutate les waypoints (`wp.flagged`) in-place ; appeler AVANT toute décision de viabilité
- Branche multi-critères : `for route in results.values(): evaluate_route(...)` puis `all(wp.flagged ...)`

**Story 2.4 / 4.1 (CLI) :**
- `dataclasses.replace(boat, draft=draft)` pour l'override draft
- `_load_boat()` retourne `(BoatProfile, loaded: bool, thresholds_dict: dict)`
- `typer.Option(False, "--flag", is_flag=True)` pour les booléens (non utilisé ici)
- `_parse_wind(wind, departure_time)` — passage du timestamp requis pour `WindCondition`

### References

- `voyageur/cli/main.py` — `plan()` : structure complète à reproduire dans `replan()`
- `voyageur/routing/isochrone.py` — `IsochroneRoutePlanner.compute()` signature
- `voyageur/routing/multi.py` — `MultiCriteriaRoutePlanner.compute_all()` signature
- `voyageur/output/formatter.py` — `format_timeline()`, `format_multi_criteria()`
- `_bmad-output/planning-artifacts/epics.md` — Story 4.4 ACs
- `_bmad-output/implementation-artifacts/4-2-multi-criteria-route-computation.md` — pattern CLI multi-critères

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Ajouté `_handle_no_viable()` (module-level avant `plan()`) et `@app.command("replan")` dans `voyageur/cli/main.py`.
- `replan` réutilise tous les helpers existants (`_parse_position`, `_parse_depart`, `_parse_wind`, `_load_boat`) et les imports lazy du même pattern que `plan()`.
- La branche multi-critères et la branche single-route sont structurées de façon identique à `plan()`.
- 59/59 tests passent, 0 violation ruff.

### File List

- `voyageur/cli/main.py` (modifié — `_handle_no_viable()` + `replan()`)
- `tests/test_cli.py` (modifié — 3 nouveaux tests)

## Change Log

- 2026-03-31 : Story 4.4 implémentée — commande `replan` + détection next viable departure
