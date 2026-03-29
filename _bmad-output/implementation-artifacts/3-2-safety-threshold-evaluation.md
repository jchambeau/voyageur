# Story 3.2: Safety Threshold Evaluation

Status: review

## Story

As JC,
I want to define maximum acceptable wind speed and tidal current speed, and have each route segment evaluated against these thresholds,
So that dangerous segments are flagged in the timeline before I depart.

## Acceptance Criteria

1. CLI accepts optional flags `--max-wind` (kn), `--max-current` (kn), `--max-dist-shelter` (NM); if present in `~/.voyageur/boat.yaml`, loaded as defaults (CLI flags override)
2. When a waypoint's wind speed exceeds `--max-wind` OR tidal current speed exceeds `--max-current`, that waypoint is flagged with a `⚠` marker in the timeline
3. The passage summary line shows the actual count of flagged segments (replaces hardcoded `Flags: 0`)
4. When ALL waypoints are flagged, a `✗` error is printed to stderr and the command exits with code 1 (FR16)
5. `--max-dist-shelter` is accepted but not implemented in MVP — a `⚠` notice on stderr is printed if it is provided
6. `tests/test_routing.py` passes: route with one flagged segment, route where all segments are flagged, route within thresholds
7. `poetry run ruff check voyageur/ tests/` reports zero violations

## Tasks / Subtasks

- [x] Mettre à jour `voyageur/models.py` (AC: 2, 3)
  - [x] Ajouter `SafetyThresholds` dataclass avec champs optionnels `max_wind_kn`, `max_current_kn`, `max_dist_shelter_nm`
  - [x] Ajouter à `Waypoint` (après `speed_over_ground`) : `tidal_current_speed: float = 0.0`, `tidal_current_direction: float = 0.0`, `flagged: bool = False`

- [x] Mettre à jour `voyageur/routing/planner.py` (AC: 2)
  - [x] Stocker les données marée dans chaque `Waypoint` : passer `tidal_current_speed=tidal_state.current_speed, tidal_current_direction=tidal_state.current_direction` à la construction
  - [x] Mettre à jour LES DEUX constructions de `Waypoint` : le cas "déjà à destination" ET le cas "arrivée en boucle" (utiliser le dernier `tidal_state` connu)
  - [x] Cas "déjà à destination" : utiliser `tidal_state` de step 1 (appel unique avant de retourner)

- [x] Implémenter `voyageur/routing/safety.py` (AC: 2, 3, 4)
  - [x] Importer `Route`, `WindCondition`, `SafetyThresholds` depuis `voyageur.models`
  - [x] Implémenter `evaluate_route(route, wind, thresholds) -> int`
  - [x] Pour chaque waypoint : flag si `wind.speed > max_wind_kn` OU `wp.tidal_current_speed > max_current_kn`
  - [x] Retourner le compte total de waypoints flagués

- [x] Mettre à jour `voyageur/output/formatter.py` (AC: 2, 3)
  - [x] Colonne TIDE : utiliser `_fmt_dir_spd(wp.tidal_current_direction, wp.tidal_current_speed)` au lieu de `"---/---"` fixe
  - [x] Ajouter marqueur `  ⚠` en fin de ligne pour les waypoints flagués (`wp.flagged is True`)
  - [x] Résumé final : remplacer `Flags: 0` par `Flags: {count}` où `count = sum(1 for wp in route.waypoints if wp.flagged)`

- [x] Mettre à jour `voyageur/cli/main.py` (AC: 1, 4, 5)
  - [x] Ajouter flags optionnels à `plan()` : `--max-wind`, `--max-current`, `--max-dist-shelter` (tous `float | None`, défaut `None`)
  - [x] Étendre `_load_boat()` pour retourner aussi les seuils boat.yaml si présents
  - [x] Si `--max-dist-shelter` fourni : émettre `⚠` stderr ("--max-dist-shelter not yet implemented — shelter data unavailable") et continuer
  - [x] Après `planner.compute()` et avant `cartography.intersects_land()` : appeler `evaluate_route()`
  - [x] Si tous les waypoints flagués → `typer.echo("✗ ...", err=True)` + `raise typer.Exit(1)`

- [x] Ajouter tests dans `tests/test_routing.py` (AC: 6)
  - [x] `test_safety_flags_exceed_wind` : `max_wind_kn=10`, vent=15 kn → tous flagués, count == len(waypoints)
  - [x] `test_safety_no_flags_within_thresholds` : `max_wind_kn=20`, vent=15 kn → 0 flagué
  - [x] `test_safety_flags_exceed_current` : mock tidal avec current=3 kn, `max_current_kn=2` → tous flagués
  - [x] `test_safety_no_thresholds_no_flags` : sans seuils → 0 flagué

- [x] Valider (AC: 7)
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run ruff check voyageur/ tests/`
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run pytest tests/ -v`

## Dev Notes

### 1. Nouveaux champs `Waypoint` dans `models.py`

`Waypoint` utilise `@dataclass(slots=True)`. Les champs **avec** défaut doivent venir **après** les champs **sans** défaut.

`Waypoint` actuel :
```python
@dataclass(slots=True)
class Waypoint:
    lat: float
    lon: float
    timestamp: datetime.datetime
    heading: float
    speed_over_ground: float
```

`Waypoint` après Story 3.2 :
```python
@dataclass(slots=True)
class Waypoint:
    lat: float
    lon: float
    timestamp: datetime.datetime
    heading: float
    speed_over_ground: float
    # champs ajoutés Story 3.2 — défauts pour rétrocompatibilité
    tidal_current_speed: float = 0.0
    tidal_current_direction: float = 0.0
    flagged: bool = False
```

> **CRITIQUE** : Tous les tests existants créent `Waypoint` avec kwargs — les défauts préservent la rétrocompatibilité complète. Aucun test existant n'est cassé.

### 2. `SafetyThresholds` dans `models.py`

```python
@dataclass(slots=True)
class SafetyThresholds:
    """Safety threshold parameters for route evaluation."""

    max_wind_kn: float | None = None
    max_current_kn: float | None = None
    max_dist_shelter_nm: float | None = None   # non implémenté MVP
```

> À placer dans `models.py` après `Route`, avant la fin du fichier.

### 3. `routing/safety.py` — implémentation complète

```python
from voyageur.models import Route, SafetyThresholds, WindCondition


def evaluate_route(
    route: Route,
    wind: WindCondition,
    thresholds: SafetyThresholds,
) -> int:
    """Flag waypoints exceeding safety thresholds. Returns flagged count.

    Mutates route.waypoints[*].flagged in place.
    """
    count = 0
    for wp in route.waypoints:
        flagged = False
        if (
            thresholds.max_wind_kn is not None
            and wind.speed > thresholds.max_wind_kn
        ):
            flagged = True
        if (
            thresholds.max_current_kn is not None
            and wp.tidal_current_speed > thresholds.max_current_kn
        ):
            flagged = True
        wp.flagged = flagged
        if flagged:
            count += 1
    return count
```

> **Note MVP** : Le vent est constant — si `max_wind_kn` est dépassé, TOUS les waypoints seront flagués. C'est intentionnel. `--max-dist-shelter` n'est pas vérifié ici (pas de données abri disponibles).

### 4. Mise à jour `planner.py` — stocker tidal dans Waypoint

La boucle appelle déjà `self._tidal.get_current()` à chaque step. Il suffit de passer les résultats au constructeur `Waypoint`.

**Waypoint dans la boucle (position courante, avant avancement) :**
```python
route.waypoints.append(
    Waypoint(
        lat=current_lat,
        lon=current_lon,
        timestamp=current_time,
        heading=heading,
        speed_over_ground=sog,
        tidal_current_speed=tidal_state.current_speed,
        tidal_current_direction=tidal_state.current_direction,
    )
)
```

**Waypoint d'arrivée (après avancement, en fin de boucle) :**
```python
route.waypoints.append(
    Waypoint(
        lat=current_lat,
        lon=current_lon,
        timestamp=current_time,
        heading=heading,
        speed_over_ground=sog,
        tidal_current_speed=tidal_state.current_speed,
        tidal_current_direction=tidal_state.current_direction,
    )
)
```

**Cas "already at destination" (avant la boucle) :**
Il faut appeler `tidal_state = self._tidal.get_current(current_lat, current_lon, current_time)` avant de créer ce waypoint unique.

```python
# Check if already at destination before the loop
_, _, init_dist = _GEOD.inv(...)
if init_dist <= ARRIVAL_TOLERANCE_M:
    tidal_state = self._tidal.get_current(current_lat, current_lon, current_time)
    route.waypoints.append(
        Waypoint(
            lat=current_lat,
            lon=current_lon,
            timestamp=current_time,
            heading=0.0,
            speed_over_ground=0.0,
            tidal_current_speed=tidal_state.current_speed,
            tidal_current_direction=tidal_state.current_direction,
        )
    )
    route.total_duration = datetime.timedelta(0)
    return route
```

### 5. Mise à jour `formatter.py`

**Colonne TIDE :** remplacer `tide = "---/---"` par :
```python
tide = _fmt_dir_spd(wp.tidal_current_direction, wp.tidal_current_speed)
```

**Marqueur flag :** ajouter `  ⚠` en fin de ligne si flagué :
```python
row = SEP.join([elapsed, lat, lon, hdg, sog, tide, wind_col])
if wp.flagged:
    row = row + "  ⚠"
lines.append(row)
```

**Résumé :** remplacer `Flags: 0` par :
```python
flag_count = sum(1 for wp in route.waypoints if wp.flagged)
lines.append(
    f"Total: {dist_nm:.1f} NM  |  Duration: {duration_str}"
    f"  |  Flags: {flag_count}"
)
```

> **Contrainte 80 colonnes** : La ligne de base est ~57 chars. `  ⚠` ajoute 3 colonnes → 60 chars max. Toujours dans la limite de 80.

### 6. Mise à jour `cli/main.py`

**Nouveaux paramètres de `plan()` :**
```python
@app.command()
def plan(
    from_port: str = typer.Option(..., "--from", help="Departure port or lat/lon"),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    depart: str = typer.Option(..., "--depart", help="Departure time (ISO 8601)"),
    wind: str = typer.Option(..., "--wind", help="Wind direction/speed (e.g. 240/15)"),
    step: int = typer.Option(15, "--step", help="Time step in minutes"),
    max_wind: float | None = typer.Option(None, "--max-wind", help="Max wind speed (kn)"),
    max_current: float | None = typer.Option(None, "--max-current", help="Max tidal current (kn)"),
    max_dist_shelter: float | None = typer.Option(
        None, "--max-dist-shelter", help="Max distance from shelter (NM)"
    ),
) -> None:
```

**Avertissement `--max-dist-shelter` :**
```python
if max_dist_shelter is not None:
    typer.echo(
        "⚠ --max-dist-shelter not yet implemented — shelter data unavailable.",
        err=True,
    )
```

**Extension de `_load_boat()`** : retourner également les seuils optionnels depuis boat.yaml :
```python
def _load_boat() -> tuple[BoatProfile, bool, dict[str, float]]:
    """Returns (profile, loaded, thresholds_dict)."""
    ...
    thresholds = {}
    if isinstance(data, dict):
        for key in ("max_wind_kn", "max_current_kn"):
            if key in data:
                thresholds[key] = float(data[key])
    return profile, True, thresholds
```

Puis dans `plan()`, fusionner seuils boat.yaml et CLI flags (CLI prioritaire) :
```python
boat, loaded, boat_thresholds = _load_boat()
thresholds = SafetyThresholds(
    max_wind_kn=max_wind if max_wind is not None else boat_thresholds.get("max_wind_kn"),
    max_current_kn=max_current if max_current is not None else boat_thresholds.get("max_current_kn"),
)
```

**Appel `evaluate_route()` et vérification "all flagged" :**
```python
from voyageur.routing.safety import evaluate_route

flag_count = evaluate_route(route, wind_condition, thresholds)
if flag_count > 0 and flag_count == len(route.waypoints):
    typer.echo(
        "✗ No viable conditions — all segments exceed safety thresholds.",
        err=True,
    )
    raise typer.Exit(1)
```

> **Ordre dans `plan()`** : appeler `evaluate_route()` APRÈS `planner.compute()` et AVANT `cartography.intersects_land()`.

### 7. Tests dans `tests/test_routing.py`

Imports à ajouter en tête du fichier (en plus des imports existants) :
```python
from voyageur.models import SafetyThresholds
from voyageur.routing.safety import evaluate_route
```

```python
def test_safety_flags_exceed_wind(mock_tidal, mock_cartography, boat, now):
    """Wind=15 kn > max_wind=10 kn → tous waypoints flagués."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_wind_kn=10.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == len(route.waypoints)
    assert all(wp.flagged for wp in route.waypoints)


def test_safety_no_flags_within_thresholds(mock_tidal, mock_cartography, boat, now):
    """Wind=15 kn < max_wind=20 kn → aucun waypoint flagué."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_wind_kn=20.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == 0
    assert not any(wp.flagged for wp in route.waypoints)


def test_safety_flags_exceed_current(mock_cartography, boat, now):
    """Courant=3 kn > max_current=2 kn → tous waypoints flagués."""
    from voyageur.models import TidalState

    class _HighCurrentTidal:
        def get_current(self, lat, lon, at):
            return TidalState(
                timestamp=at, current_direction=90.0,
                current_speed=3.0, water_height=0.0,
            )

    planner = RoutePlanner(tidal=_HighCurrentTidal(), cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds(max_current_kn=2.0)
    count = evaluate_route(route, wind, thresholds)
    assert count == len(route.waypoints)


def test_safety_no_thresholds_no_flags(mock_tidal, mock_cartography, boat, now):
    """Sans seuils définis → aucun waypoint flagué."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat,
    )
    thresholds = SafetyThresholds()  # aucun seuil
    count = evaluate_route(route, wind, thresholds)
    assert count == 0
```

### 8. Fichiers à modifier / créer

| Action | Fichier |
|--------|---------|
| Modifier | `voyageur/models.py` — `Waypoint` (3 champs) + `SafetyThresholds` dataclass |
| Modifier | `voyageur/routing/planner.py` — stocker tidal dans Waypoint (3 endroits) |
| Implémenter | `voyageur/routing/safety.py` — `evaluate_route()` (placeholder existant) |
| Modifier | `voyageur/output/formatter.py` — TIDE réel, marqueur ⚠, Flags count |
| Modifier | `voyageur/cli/main.py` — 3 nouveaux flags, `evaluate_route()`, exit 1 si all-flagged |
| Modifier | `tests/test_routing.py` — 4 nouveaux tests |

### 9. Fichiers à NE PAS toucher

- `voyageur/cartography/` — ne pas modifier
- `voyageur/tidal/` — ne pas modifier
- `tests/conftest.py` — ne pas modifier (les mocks existants fonctionnent avec les nouveaux champs Waypoint)
- `tests/test_models.py`, `tests/test_tidal.py`, `tests/test_cartography.py`, `tests/test_output.py` — ne pas modifier

### 10. Rétrocompatibilité garantie

Les mocks dans `conftest.py` (`_ZeroTidalProvider`) retournent `current_speed=0.0`. Après la mise à jour du planner, les waypoints des tests existants auront `tidal_current_speed=0.0` — **aucun test existant ne casse**.

Le formatter lit `wp.tidal_current_direction` et `wp.tidal_current_speed` — avec les défauts `0.0`, les tests de `test_output.py` qui construisent des `Waypoint` directement obtiendront `"  0/0.0"` à la place de `"---/---"`. Vérifier que `test_output.py` accepte ce changement ou adapter les assertions.

> **Analyse de `tests/test_output.py`** : `test_wind_none_placeholder` vérifie `"---/---" in output` — cette assertion teste la colonne WIND (pas TIDE). Quand `wind=None`, le WIND affiche `"---/---"` ; le TIDE affiche `"  0/0.0"` (mock retourne 0.0). L'assertion passe sans modification. `test_80_col_constraint` ne sera pas affecté non plus (aucun waypoint flagué dans les fixtures existantes). **Aucune modification de `tests/test_output.py` n'est requise.**

### 11. Dépendances

Aucune nouvelle dépendance — uniquement des modules stdlib + existants.

### 12. Learnings des stories précédentes

**Story 3.1 :**
- `export PATH="$HOME/.local/bin:$PATH"` avant poetry
- Lazy imports dans `plan()` — ajouter `evaluate_route` dans le bloc d'imports lazy

**Story 2.4 :**
- `_load_boat()` signature change → les deux call-sites dans `plan()` doivent être mis à jour (destructuration du tuple retourné)
- Typer flags optionnels : `float | None = typer.Option(None, "--flag-name", ...)`

**Projet :**
- `@dataclass(slots=True)` : champs avec défaut après champs sans défaut
- `typer.echo(msg, err=True)` pour stderr
- `raise typer.Exit(1)` pour exit code 1 — jamais `sys.exit()`
- `print()` interdit partout

### References

- Architecture : `_bmad-output/planning-artifacts/architecture.md` — routing/safety.py section
- Models : `voyageur/models.py` — Waypoint, Route
- Planner : `voyageur/routing/planner.py` — boucle principale
- Formatter : `voyageur/output/formatter.py` — TIDE column + summary
- Story 3.1 : `_bmad-output/implementation-artifacts/3-1-coastal-obstacle-detection.md`
- conftest : `tests/conftest.py` — fixtures mock_tidal, mock_cartography
- test_output.py : vérifier assertions TIDE avant de modifier le formatter

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tous les ACs satisfaits. 44 tests passent (+4 nouveaux), ruff 0 violations.
- `models.py` : `Waypoint` étendu avec 3 champs (défaut = rétrocompatibilité totale) ; `SafetyThresholds` ajouté.
- `planner.py` : tidal stocké dans chaque Waypoint (3 constructions mises à jour, dont le cas "already at destination").
- `safety.py` : `evaluate_route()` — mutate `wp.flagged` en place, retourne le count.
- `formatter.py` : colonne TIDE affiche les vraies données tidal ; `⚠` par ligne si flagué ; `Flags: N` dans le résumé.
- `cli/main.py` : 3 nouveaux flags optionnels ; `_load_boat()` retourne maintenant un tuple de 3 éléments ; `evaluate_route()` appelé avant `intersects_land()` ; exit 1 si all-flagged.
- `--max-dist-shelter` : accepté mais non implémenté (avertissement stderr).

### File List

- `voyageur/models.py` (modifié — Waypoint + SafetyThresholds)
- `voyageur/routing/planner.py` (modifié — tidal dans Waypoint)
- `voyageur/routing/safety.py` (implémenté — evaluate_route)
- `voyageur/output/formatter.py` (modifié — TIDE réel, marqueur ⚠, Flags count)
- `voyageur/cli/main.py` (modifié — 3 nouveaux flags, evaluate_route, exit 1)
- `tests/test_routing.py` (modifié — 4 nouveaux tests safety)
