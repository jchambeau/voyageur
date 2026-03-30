# Story 4.2: Multi-Criteria Route Computation

Status: review

## Story

As JC,
I want the system to compute and display multiple route options simultaneously — fastest, comfort, shelter, traffic —
so that I can choose the route that best fits conditions and my preferences for each passage.

## Acceptance Criteria

1. Given a passage request with `--criteria all` (or individual values: `fastest`, `comfort`, `shelter`, `traffic`), when the route planning command runs, then up to four routes are computed and displayed sequentially with distinct labels
2. The fastest route picks the heading closest to direct bearing among obstacle-free candidates (current `IsochroneRoutePlanner` behavior, made explicit)
3. The comfort route picks the heading with TWA closest to 90° (beam reach) among obstacle-free candidates
4. The shelter route picks the heading whose projected next position is closest to the nearest Norman coast harbour among obstacle-free candidates
5. The traffic criterion has no shipping lane data available — it falls back to fastest behavior with a `⚠ traffic: no shipping lane data` notice on stderr
6. When `--criteria` is not provided, CLI behavior is unchanged (single fastest route, no label)
7. `tests/test_routing.py` passes: multi-criteria output for a Cherbourg→Granville scenario returns at least two distinct routes (fastest ≠ comfort); `poetry run ruff check voyageur/ tests/` returns zero violations

## Tasks / Subtasks

- [x] Créer `voyageur/routing/multi.py` — `MultiCriteriaRoutePlanner` (AC: 1, 2, 3, 4, 5)
  - [x] Même structure de boucle que `IsochroneRoutePlanner` mais collecte TOUS les headings viables (ne break pas au premier)
  - [x] `_score_heading(viable, direct_bearing, wind, current_lat, current_lon, criterion, distance_m)` — sélectionne le meilleur heading selon le critère
  - [x] Critère `fastest` : `min(viable, key=lambda h: abs((h - direct_bearing + 180) % 360 - 180))`
  - [x] Critère `comfort` : `min(viable, key=lambda h: abs(_twa(wind.direction, h) - 90.0))`
  - [x] Critère `shelter` : `min(viable, key=lambda h: _shelter_dist(h, current_lat, current_lon, distance_m))`
  - [x] Critère `traffic` : identique à `fastest` (stub documenté — pas de données shipping lanes)
  - [x] `compute_all(criteria, origin, destination, departure_time, wind, boat, step_minutes) -> dict[str, Route]`
  - [x] Constante `CRITERIA = ("fastest", "comfort", "shelter", "traffic")`
  - [x] Constante `HARBOURS: dict[str, tuple[float, float]]` — copie des ports normands (voir ci-dessous)

- [x] Modifier `voyageur/output/formatter.py` — ajouter `format_multi_criteria()` (AC: 1)
  - [x] `format_multi_criteria(results: dict[str, Route], wind: WindCondition | None = None) -> str`
  - [x] Pour chaque label/route : `=== FASTEST ===\n{format_timeline(route, wind)}`
  - [x] Sections séparées par `\n\n`

- [x] Modifier `voyageur/cli/main.py` — ajouter `--criteria` (AC: 1, 5, 6)
  - [x] `criteria: str | None = typer.Option(None, "--criteria", help="Route criteria: fastest,comfort,shelter,traffic or all")`
  - [x] Parser : `"all"` → `list(CRITERIA)` ; sinon `[c.strip() for c in criteria.split(",")]`
  - [x] Valider chaque criterion contre `CRITERIA` tuple, erreur si invalide
  - [x] Si criteria None → comportement inchangé (`IsochroneRoutePlanner`, `format_timeline`)
  - [x] Si criteria défini → `MultiCriteriaRoutePlanner`, `format_multi_criteria`
  - [x] Si `"traffic"` dans criteria → `typer.echo("⚠ traffic: no shipping lane data — falls back to fastest", err=True)`
  - [x] Import lazy de `MultiCriteriaRoutePlanner` dans `plan()` (même pattern que les autres imports lazy)

- [x] Modifier `tests/test_routing.py` — nouveaux tests multi-critères (AC: 7)
  - [x] `test_multi_criteria_fastest_and_comfort_are_distinct` : `compute_all(["fastest", "comfort"])`, vérifier que `fastest.waypoints[0].heading != comfort.waypoints[0].heading`
  - [x] `test_multi_criteria_all_returns_four_routes` : `compute_all(list(CRITERIA))`, vérifier que `len(results) == 4` et chaque valeur est une `Route`

- [x] Valider (AC: 7)
  - [x] `poetry run ruff check voyageur/ tests/`
  - [x] `poetry run pytest tests/ -v`

## Dev Notes

### 1. Architecture du `MultiCriteriaRoutePlanner`

Différence clé avec `IsochroneRoutePlanner` : au lieu de `break` sur le premier heading valide, on collecte TOUS les headings viables puis on sélectionne selon le critère.

```python
# Dans la boucle principale, étape beam search :
viable: list[float] = []
distance_m = btw * KNOTS_TO_MPS * step_sec
if distance_m > 0.0:
    for offset in _HEADING_OFFSETS:
        candidate = (direct_bearing + offset) % 360.0
        cand_lon, cand_lat, _ = _GEOD.fwd(
            current_lon, current_lat, candidate, distance_m
        )
        if not self._segment_crosses_land(
            current_lat, current_lon, cand_lat, cand_lon, current_time
        ):
            viable.append(candidate)

if not viable:
    heading = direct_bearing  # fallback cas dégénéré
else:
    heading = self._score_heading(
        viable, direct_bearing, wind, current_lat, current_lon, criterion, distance_m
    )
```

### 2. Fonctions de scoring

```python
def _twa(wind_direction: float, heading: float) -> float:
    """True Wind Angle [0, 180] for given heading."""
    twa = (wind_direction - heading) % 360.0
    return twa if twa <= 180.0 else 360.0 - twa


def _score_heading(
    self,
    viable: list[float],
    direct_bearing: float,
    wind: WindCondition,
    current_lat: float,
    current_lon: float,
    criterion: str,
    distance_m: float,
) -> float:
    if criterion in ("fastest", "traffic"):
        # Minimize angular deviation from direct bearing
        return min(
            viable,
            key=lambda h: abs((h - direct_bearing + 180.0) % 360.0 - 180.0),
        )
    elif criterion == "comfort":
        # Prefer beam reach (TWA ≈ 90°)
        return min(viable, key=lambda h: abs(_twa(wind.direction, h) - 90.0))
    elif criterion == "shelter":
        return min(
            viable,
            key=lambda h: self._shelter_dist(h, current_lat, current_lon, distance_m),
        )
    return viable[0]  # fallback
```

### 3. Critère shelter — calcul de proximité

```python
def _shelter_dist(
    self,
    candidate: float,
    current_lat: float,
    current_lon: float,
    distance_m: float,
) -> float:
    """Distance (m) to nearest harbour after moving 'distance_m' along candidate."""
    if distance_m <= 0.0:
        return float("inf")
    cand_lon, cand_lat, _ = _GEOD.fwd(
        current_lon, current_lat, candidate, distance_m
    )
    return min(
        _GEOD.inv(cand_lon, cand_lat, hlon, hlat)[2]
        for hlat, hlon in self._harbours.values()
    )
```

> **Attention** : `_GEOD.inv(lon1, lat1, lon2, lat2)` → retourne `(fwd_az, back_az, dist_m)`. Passer lon avant lat (même convention que `planner.py`).

### 4. Constante `HARBOURS` dans `multi.py`

Copie des ports depuis `cli/main.py` (ne pas importer depuis CLI dans le routing) :

```python
HARBOURS: dict[str, tuple[float, float]] = {
    "cherbourg":             (49.6453, -1.6222),
    "granville":             (48.8327, -1.5971),
    "le havre":              (49.4892,  0.1080),
    "saint-malo":            (48.6490, -1.9800),
    "barfleur":              (49.6733, -1.2638),
    "saint-vaast-la-hougue": (49.5875, -1.2703),
    "honfleur":              (49.4189,  0.2337),
}
```

### 5. Constante `_HEADING_OFFSETS`

Ne pas importer depuis `isochrone.py` (module interne). Redéfinir dans `multi.py` — c'est une constante triviale, pas une abstraction partagée.

```python
_HEADING_OFFSETS: tuple[float, ...] = (
    0.0,
    15.0, -15.0,
    30.0, -30.0,
    45.0, -45.0,
    60.0, -60.0,
    75.0, -75.0,
    90.0, -90.0,
)
```

### 6. Imports dans `multi.py`

```python
import datetime
import math

from pyproj import Geod

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import BoatProfile, Route, Waypoint, WindCondition
from voyageur.routing.planner import (
    ARRIVAL_TOLERANCE_M,
    KNOTS_TO_MPS,
    MAX_STEPS,
    _polar_fraction,
)
from voyageur.tidal.protocol import TidalProvider
```

Imports identiques à `isochrone.py`. Ruff : stdlib → third-party → first-party, lignes ≤ 88 chars.

### 7. Boucle principale — réutilisation maximale de `isochrone.py`

La boucle de `MultiCriteriaRoutePlanner._compute_one()` est quasi-identique à `IsochroneRoutePlanner.compute()`. Seule l'étape 4 (beam search) change : collecte de tous les headings viables + scoring. Copier la structure complète de `isochrone.py` et modifier uniquement cette étape.

Étapes :
1. Tidal current
2. Direct bearing
3. BTW from polar model (identique)
4. **Beam search modifié** : collect viables + score (différent)
5. Vector addition boat + tide → SOG + COG (identique)
6. Record Waypoint (identique)
7. Advance position (identique)
8. Check arrival (identique)

### 8. `compute_all()` — signature

```python
CRITERIA: tuple[str, ...] = ("fastest", "comfort", "shelter", "traffic")


def compute_all(
    self,
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure_time: datetime.datetime,
    wind: WindCondition,
    boat: BoatProfile,
    step_minutes: int = 15,
    criteria: list[str] | None = None,
) -> dict[str, Route]:
    """Compute routes for each criterion. Returns {criterion: Route}."""
    if criteria is None:
        criteria = list(CRITERIA)
    return {
        c: self._compute_one(
            origin, destination, departure_time, wind, boat, step_minutes, c
        )
        for c in criteria
    }
```

### 9. `format_multi_criteria()` dans `formatter.py`

```python
def format_multi_criteria(
    results: dict[str, Route],
    wind: WindCondition | None = None,
) -> str:
    """Format multiple routes, one section per criterion."""
    sections = []
    for label, route in results.items():
        header = f"=== {label.upper()} ==="
        sections.append(header + "\n" + format_timeline(route, wind))
    return "\n\n".join(sections)
```

### 10. Modification CLI `plan()`

Ajouter le paramètre après les existants :

```python
criteria: str | None = typer.Option(
    None, "--criteria",
    help="Route criteria: fastest,comfort,shelter,traffic or all",
),
```

Dans le corps de `plan()`, après les validations existantes et avant le bloc d'imports lazy :

```python
criteria_list: list[str] | None = None
if criteria is not None:
    from voyageur.routing.multi import CRITERIA as _ALL_CRITERIA
    raw = list(_ALL_CRITERIA) if criteria.strip() == "all" else [
        c.strip() for c in criteria.split(",")
    ]
    invalid = [c for c in raw if c not in _ALL_CRITERIA]
    if invalid:
        typer.echo(
            f"✗ Unknown criteria: {', '.join(invalid)}. "
            f"Valid: {', '.join(_ALL_CRITERIA)}",
            err=True,
        )
        raise typer.Exit(1)
    if "traffic" in raw:
        typer.echo(
            "⚠ traffic: no shipping lane data — falls back to fastest",
            err=True,
        )
    criteria_list = raw
```

Dans le bloc d'imports lazy :

```python
from voyageur.cartography.impl import GeoJsonCartography
from voyageur.output.formatter import format_multi_criteria, format_timeline
from voyageur.routing.isochrone import IsochroneRoutePlanner
from voyageur.routing.multi import MultiCriteriaRoutePlanner
from voyageur.routing.safety import evaluate_route
from voyageur.tidal.impl import HarmonicTidalModel
```

Remplacer le bloc planner + format_timeline par :

```python
cartography = GeoJsonCartography()
tidal = HarmonicTidalModel()

if criteria_list is not None:
    multi = MultiCriteriaRoutePlanner(tidal=tidal, cartography=cartography)
    results = multi.compute_all(
        origin=origin,
        destination=destination,
        departure_time=departure_time,
        wind=wind_condition,
        boat=boat,
        step_minutes=step,
        criteria=criteria_list,
    )
    # Safety eval on fastest route (first criterion)
    first_route = next(iter(results.values()))
    flag_count = evaluate_route(first_route, wind_condition, thresholds)
    if flag_count > 0 and flag_count == len(first_route.waypoints):
        typer.echo(
            "✗ No viable conditions — all segments exceed safety thresholds.",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(format_multi_criteria(results, wind=wind_condition))
else:
    planner = IsochroneRoutePlanner(tidal=tidal, cartography=cartography)
    route = planner.compute(
        origin=origin,
        destination=destination,
        departure_time=departure_time,
        wind=wind_condition,
        boat=boat,
        step_minutes=step,
    )
    flag_count = evaluate_route(route, wind_condition, thresholds)
    if flag_count > 0 and flag_count == len(route.waypoints):
        typer.echo(
            "✗ No viable conditions — all segments exceed safety thresholds.",
            err=True,
        )
        raise typer.Exit(1)
    if cartography.intersects_land(route.waypoints):
        # ... existing land-cross warning (inchangé)
    typer.echo(format_timeline(route, wind=wind_condition))
```

> **Important** : Le check `intersects_land` post-hoc n'est appliqué qu'en mode single-route (comportement inchangé). En mode multi-critères, ne pas appliquer (complexité non justifiée).

### 11. Tests — structure

```python
from voyageur.routing.multi import CRITERIA, MultiCriteriaRoutePlanner


def test_multi_criteria_fastest_and_comfort_are_distinct(
    mock_tidal, mock_cartography, boat, now
):
    """Fastest et comfort doivent sélectionner des headings différents."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = MultiCriteriaRoutePlanner(
        tidal=mock_tidal, cartography=mock_cartography
    )
    results = planner.compute_all(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
        criteria=["fastest", "comfort"],
    )
    assert "fastest" in results
    assert "comfort" in results
    fastest = results["fastest"]
    comfort = results["comfort"]
    assert isinstance(fastest, Route)
    assert isinstance(comfort, Route)
    # Pour Cherbourg→Granville bearing ≈ 178°, vent 240° :
    # - fastest : heading ≈ 178° (closest to direct)
    # - comfort : heading ≈ 150° (TWA ≈ 90°)
    assert fastest.waypoints[0].heading != comfort.waypoints[0].heading


def test_multi_criteria_all_returns_four_routes(
    mock_tidal, mock_cartography, boat, now
):
    """compute_all avec tous les critères retourne 4 routes."""
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = MultiCriteriaRoutePlanner(
        tidal=mock_tidal, cartography=mock_cartography
    )
    results = planner.compute_all(
        origin=CHERBOURG,
        destination=GRANVILLE,
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(results) == len(CRITERIA)
    for label, route in results.items():
        assert isinstance(route, Route), f"{label}: expected Route"
        assert len(route.waypoints) >= 1, f"{label}: no waypoints"
```

> **Vérification de la distinction fastest vs comfort** : avec vent=240° et bearing direct ≈ 178°, TWA direct = `(240-178) % 360 = 62°` (close-hauled). Comfort préfère TWA ≈ 90° → heading ≈ `240-90 = 150°`. Heading fastest ≈ 178°. Différence ≈ 28° → assertion `!=` passe.

### 12. Ordre lon/lat dans pyproj (rappel critique)

```python
# _GEOD.inv(lon1, lat1, lon2, lat2) → (fwd_az, back_az, dist_m)
# _GEOD.fwd(lon, lat, az, dist_m)   → (new_lon, new_lat, back_az)
```

Toujours passer lon avant lat — même convention que dans `planner.py` et `isochrone.py`.

### 13. Fichiers à modifier/créer

| Action | Fichier |
|--------|---------|
| Créer | `voyageur/routing/multi.py` |
| Modifier | `voyageur/output/formatter.py` — ajouter `format_multi_criteria()` |
| Modifier | `voyageur/cli/main.py` — `--criteria` option + logique multi |
| Modifier | `tests/test_routing.py` — 2 nouveaux tests |

### 14. Fichiers à NE PAS toucher

- `voyageur/models.py` — aucun nouveau champ requis
- `voyageur/routing/isochrone.py` — ne pas modifier (conservé pour single-route)
- `voyageur/routing/planner.py` — conservé intact (source de constantes et `_polar_fraction`)
- `voyageur/cartography/protocol.py`, `impl.py` — non concernés
- `voyageur/routing/safety.py` — non concerné
- `tests/test_cli.py`, `tests/test_tidal.py` — ne pas modifier

### 15. Apprentissages stories précédentes

**Story 4.1 (isochrone) :**
- `_segment_crosses_land` : crée deux `Waypoint` minimaux (heading=0, sog=0) pour appeler `intersects_land([a, b])` — réutiliser même pattern
- `_GEOD.fwd()` : retourne `(new_lon, new_lat, back_az)` — déstructuration `new_lon, new_lat, _ = _GEOD.fwd(...)`
- Ruff : imports dans l'ordre stdlib → pyproj → voyageur ; lignes ≤ 88 chars

**Story 2.2 (routing) :**
- `_polar_fraction` : angle < 45° → 0.0, 45°-90° → 0.45, 90°-135° → 0.50, > 135° → 0.40
- Vector addition : toujours bot_n + tide_n, bot_e + tide_e → sog = hypot

**Story 2.4 (CLI) :**
- Imports lazy dans `plan()` : tout importer dans le corps de la fonction, pas au top-level
- `typer.Option(..., err=True)` pour messages d'erreur → stderr

### References

- `voyageur/routing/isochrone.py` — boucle principale à copier et adapter
- `voyageur/routing/planner.py` — `_polar_fraction`, `KNOTS_TO_MPS`, `ARRIVAL_TOLERANCE_M`, `MAX_STEPS`
- `voyageur/output/formatter.py` — `format_timeline()` à appeler dans `format_multi_criteria()`
- `voyageur/cli/main.py` — pattern d'imports lazy et structure `plan()`
- `_bmad-output/planning-artifacts/epics.md` — Story 4.2 ACs
- `_bmad-output/implementation-artifacts/4-1-isochrone-grid-with-obstacle-avoidance.md` — notes dev 4.1

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tous les ACs satisfaits. 54 tests passent (+2 nouveaux story 4.2), ruff 0 violations.
- `MultiCriteriaRoutePlanner` dans `multi.py` : même boucle que `IsochroneRoutePlanner` mais collecte tous les headings viables avant de scorer. Critères fastest/traffic = déviation minimale du bearing direct ; comfort = TWA le plus proche de 90° ; shelter = position suivante la plus proche d'un port normand.
- `format_multi_criteria()` ajoutée dans `formatter.py` : sections `=== CRITERION ===` séparées par `\n\n`.
- CLI : `--criteria fastest,comfort,shelter,traffic|all` ; comportement single-route inchangé si absent ; warning stderr pour traffic (pas de données lanes).

### File List

- `voyageur/routing/multi.py` (créé)
- `voyageur/output/formatter.py` (modifié — `format_multi_criteria()`)
- `voyageur/cli/main.py` (modifié — `--criteria` option)
- `tests/test_routing.py` (modifié — 2 nouveaux tests multi-critères)
