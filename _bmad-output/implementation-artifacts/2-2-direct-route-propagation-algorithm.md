# Story 2.2: Direct Route Propagation Algorithm

Status: done

## Story

As JC,
I want the system to compute a time-stepped route by combining wind and tidal current at each step,
So that I can see my estimated position at every interval throughout my passage.

## Acceptance Criteria

1. Given an origin, destination, departure_time, wind (direction + speed), step_minutes, and injected `TidalProvider` and `CartographyProvider`, when `RoutePlanner.compute()` is called, it returns a `Route` with one `Waypoint` per time step from origin to destination
2. Each `Waypoint` has lat, lon, timestamp, heading, and speed_over_ground computed from wind vector + tidal current vector
3. Boat speed through water is derived from the `BoatProfile` simplified polar model (fraction of wind speed based on True Wind Angle)
4. The route terminates when destination is reached (within 500 m tolerance) or `MAX_STEPS` is exceeded
5. `tests/test_routing.py` passes a Cherbourg→Granville scenario with mock `TidalProvider` and mock `CartographyProvider`
6. Computation of a Cherbourg→Le Havre passage (~85 NM) at 15-min step completes in under 5 s (NFR1)
7. `poetry run ruff check voyageur/ tests/` reports zero violations

## Tasks / Subtasks

- [x] Implémenter `voyageur/routing/planner.py` (AC: 1, 2, 3, 4)
  - [x] Constantes module-level : `KNOTS_TO_MPS`, `ARRIVAL_TOLERANCE_M`, `MAX_STEPS`, `_GEOD`
  - [x] Helper `_polar_fraction(wind_angle_deg: float) -> float`
  - [x] `RoutePlanner.__init__(tidal: TidalProvider, cartography: CartographyProvider)`
  - [x] `RoutePlanner.compute(origin, destination, departure_time, wind, boat, step_minutes=15) -> Route`
  - [x] Boucle de propagation : tidal + vent → vecteurs → SOG + COG → avance position
  - [x] Normalisation heading dans [0, 360) à chaque étape
  - [x] `Route.total_duration` calculé et positif à la fin de la boucle

- [x] Ajouter fixtures mock dans `tests/conftest.py` (prérequis test_routing.py)
  - [x] Classe `_ZeroTidalProvider` (retourne `TidalState` courant nul)
  - [x] Classe `_NoObstacleCartographyProvider` (retourne `False`)
  - [x] Fixtures `mock_tidal` et `mock_cartography`

- [x] Créer `tests/test_routing.py` (AC: 5, 6)
  - [x] Test happy path Cherbourg→Granville : route non vide, waypoints valides
  - [x] Test validité de chaque waypoint (lat/lon/timestamp/heading/sog)
  - [x] Test performance NFR1 : Cherbourg→Le Havre à 15 min step < 5 s
  - [x] Test vent nul + courant nul : route atteint MAX_STEPS, pas d'erreur
  - [x] Test timestamps : chaque waypoint = t₀ + n × step_minutes

- [x] Valider (AC: 7)
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run ruff check voyageur/ tests/`
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run pytest tests/ -v`

## Dev Notes

### Fichier cible : `voyageur/routing/planner.py`

Ce fichier est actuellement un stub `# Placeholder — implemented in Story 2.2`. Le remplacer entièrement.

### Algorithme de propagation

À chaque étape `i` :
1. Appel `TidalProvider.get_current(lat, lon, timestamp)` — toujours à la position et heure courantes
2. Cap vers la destination via `_GEOD.inv(current_lon, current_lat, dest_lon, dest_lat)` → `fwd_az`
3. Calcul TWA (True Wind Angle) → fraction polaire → BTW (boat speed through water, knots)
4. Addition vectorielle : vitesse bateau + courant tidal → COG + SOG
5. Avancement position via `_GEOD.fwd(current_lon, current_lat, cog_deg, distance_m)`
6. Enregistrement `Waypoint` avec position courante (AVANT avancement), heading vers destination, SOG
7. Vérification arrivée : distance restante ≤ 500 m → ajouter waypoint final, sortir

### Ordre des arguments pyproj — CRITIQUE

```python
# inv : longitude PREMIER (même convention que Story 2.1)
fwd_az, _, dist_m = _GEOD.inv(lon1, lat1, lon2, lat2)

# fwd : longitude PREMIER
lon2, lat2, _ = _GEOD.fwd(current_lon, current_lat, azimuth_deg, distance_m)
```

Inverser lat/lon provoque des calculs silencieusement erronés — pas d'exception levée.

### `fwd_az` de `inv()` — normalisation obligatoire

`Geod.inv()` retourne `fwd_az ∈ [-180, 180]`. Normaliser immédiatement :

```python
heading = fwd_az % 360.0  # toujours [0, 360)
```

Ceci est la correction listée dans deferred-work.md : "Heading/direction fields acceptent valeurs hors [0, 360) — normalisation = module routing (Story 2.2)".

### Modèle polaire simplifié

BTW = wind_speed × polar_fraction(TWA) où :

```
TWA (True Wind Angle, [0, 180]) → fraction
  [  0,  45°) → 0.00  (vent debout — irons, impossible de naviguer)
  [ 45,  90°) → 0.45  (proche du lit)
  [ 90, 135°) → 0.50  (travers — point le plus rapide)
  [135, 180°) → 0.40  (grand largue / vent arrière)
```

**Calcul du TWA :**

```python
twa = (wind.direction - heading) % 360.0  # [0, 360)
if twa > 180.0:
    twa = 360.0 - twa
# Maintenant twa ∈ [0, 180] (symétrie tribord/bâbord)
```

La `BoatProfile` n'a pas de champ hull_speed — utiliser fraction du vent uniquement. `sail_area` et `loa` sont ignorés dans le modèle simplifié.

### Addition vectorielle vent + tidal

```python
import math

# Décomposer en composantes N/E (knots)
boat_n = btw * math.cos(math.radians(heading))
boat_e = btw * math.sin(math.radians(heading))
tide_n = tidal_state.current_speed * math.cos(math.radians(tidal_state.current_direction))
tide_e = tidal_state.current_speed * math.sin(math.radians(tidal_state.current_direction))

total_n = boat_n + tide_n
total_e = boat_e + tide_e

sog = math.hypot(total_n, total_e)                              # vitesse sur le fond (kn)
cog = math.degrees(math.atan2(total_e, total_n)) % 360.0       # cap sur le fond (°)
```

Convention : heading/current_direction = azimut True Nord (0° = Nord, 90° = Est). `math.cos` = composante Nord, `math.sin` = composante Est dans cette convention.

### Avancement de position

```python
KNOTS_TO_MPS: float = 0.514444  # 1 nœud = 0.514444 m/s

distance_m = sog * KNOTS_TO_MPS * step_sec  # step_sec = step_minutes * 60

if distance_m > 0.0:
    lon2, lat2, _ = _GEOD.fwd(current_lon, current_lat, cog, distance_m)
else:
    lon2, lat2 = current_lon, current_lat   # vent nul + courant nul → pas de mouvement
```

### Gestion du `Route.total_duration`

`total_duration` est `datetime.timedelta`. La cohérence est garantie par le routing module (deferred-work.md). Calculer à la fin de la boucle :

```python
route.total_duration = current_time - departure_time
```

`current_time` est mis à jour à chaque step **après** enregistrement du waypoint — sa valeur finale correspond au timestamp du dernier waypoint + un step.

### Structure de la boucle principale

```python
for _ in range(MAX_STEPS):
    # 1. tidal state à la position courante
    tidal_state = self._tidal.get_current(current_lat, current_lon, current_time)

    # 2. cap + distance vers destination
    fwd_az, _, dist_m = _GEOD.inv(current_lon, current_lat, destination[1], destination[0])
    heading = fwd_az % 360.0

    # 3. TWA → BTW
    twa = (wind.direction - heading) % 360.0
    if twa > 180.0:
        twa = 360.0 - twa
    btw = wind.speed * _polar_fraction(twa)

    # 4. Vecteurs → SOG, COG
    ...

    # 5. Enregistrer le waypoint AVANT l'avancement (position actuelle)
    route.waypoints.append(Waypoint(
        lat=current_lat, lon=current_lon,
        timestamp=current_time, heading=heading, speed_over_ground=sog,
    ))

    # 6. Avancer la position
    current_time += datetime.timedelta(seconds=step_sec)
    if distance_m > 0.0:
        current_lon, current_lat = lon2, lat2

    # 7. Vérifier arrivée (distance restante)
    _, _, remaining_m = _GEOD.inv(current_lon, current_lat, destination[1], destination[0])
    if remaining_m <= ARRIVAL_TOLERANCE_M:
        route.waypoints.append(Waypoint(
            lat=current_lat, lon=current_lon,
            timestamp=current_time, heading=heading, speed_over_ground=sog,
        ))
        break

route.total_duration = current_time - departure_time
```

### Vérification arrivée AVANT la boucle

Si l'origine est déjà à destination (≤ 500 m), retourner immédiatement un `Route` avec un seul waypoint :

```python
_, _, init_dist = _GEOD.inv(origin[1], origin[0], destination[1], destination[0])
if init_dist <= ARRIVAL_TOLERANCE_M:
    route.waypoints.append(Waypoint(lat=origin[0], lon=origin[1],
        timestamp=departure_time, heading=0.0, speed_over_ground=0.0))
    return route
```

### Imports ruff-conformes dans `planner.py`

```python
import datetime     # stdlib
import math         # stdlib
                    # ← ligne vide
from pyproj import Geod   # third-party
                    # ← ligne vide
from voyageur.cartography.protocol import CartographyProvider  # first-party
from voyageur.models import BoatProfile, Route, Waypoint, WindCondition
from voyageur.tidal.protocol import TidalProvider
```

Ne jamais importer `HarmonicTidalModel` directement dans `routing/` — uniquement le Protocol.

### Fixtures mock dans `tests/conftest.py`

Ajouter à la fin du `conftest.py` existant (NE PAS remplacer la fixture `now` existante) :

```python
import datetime

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import TidalState, Waypoint
from voyageur.tidal.protocol import TidalProvider


class _ZeroTidalProvider:
    """Mock TidalProvider returning zero-current TidalState for routing tests."""

    def get_current(self, lat: float, lon: float, at: datetime.datetime) -> TidalState:
        """Return a zero-current TidalState."""
        return TidalState(
            timestamp=at, current_direction=0.0, current_speed=0.0, water_height=0.0
        )


class _NoObstacleCartographyProvider:
    """Mock CartographyProvider returning False for all routes."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        """Return False — no obstacles."""
        return False


@pytest.fixture
def mock_tidal() -> TidalProvider:
    """Zero-current TidalProvider for routing tests."""
    return _ZeroTidalProvider()


@pytest.fixture
def mock_cartography() -> CartographyProvider:
    """No-obstacle CartographyProvider for routing tests."""
    return _NoObstacleCartographyProvider()
```

Attention : `conftest.py` importe déjà `datetime` et `pytest` — ne pas les dupliquer. Ajouter uniquement les imports manquants.

### Coordonnées de référence pour les tests

```python
CHERBOURG   = (49.6453, -1.6222)   # (lat, lon)
GRANVILLE   = (48.8327, -1.5971)   # ~55 NM au sud
LE_HAVRE    = (49.4892,  0.1080)   # ~85 NM à l'est (pour test NFR1)
SAINT_MALO  = (48.6490, -1.9800)   # ~70 NM au SO
```

### Test de performance NFR1

```python
import time

def test_performance_nfr1(mock_tidal, mock_cartography, now):
    """100 NM passage at 15-min step must complete in under 5 s (NFR1)."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    boat = BoatProfile(name="Test", loa=12.0, draft=1.8, sail_area=65.0, default_step=15)
    start = time.perf_counter()
    route = planner.compute(
        origin=CHERBOURG, destination=LE_HAVRE,
        departure_time=now, wind=wind, boat=boat, step_minutes=15,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"NFR1 violated: {elapsed:.2f}s (limit: 5s)"
    assert len(route.waypoints) > 0
```

### Test vent nul + courant nul

```python
def test_zero_wind_zero_current(mock_tidal, mock_cartography, now):
    """With no wind and zero tidal (mock), route hits MAX_STEPS without error."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=0.0, speed=0.0)
    boat = BoatProfile(name="Test", loa=12.0, draft=1.8, sail_area=65.0, default_step=15)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat, step_minutes=15,
    )
    # Should return a partial route, not raise
    assert isinstance(route, Route)
    assert len(route.waypoints) <= MAX_STEPS + 2  # +2 for edge cases
```

### Test timestamps incrémentaux

```python
def test_waypoint_timestamps_increment(mock_tidal, mock_cartography, now):
    """Each waypoint timestamp must increase by exactly step_minutes."""
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    boat = BoatProfile(name="Test", loa=12.0, draft=1.8, sail_area=65.0, default_step=15)
    route = planner.compute(
        origin=CHERBOURG, destination=GRANVILLE,
        departure_time=now, wind=wind, boat=boat, step_minutes=15,
    )
    step = datetime.timedelta(minutes=15)
    for i, wp in enumerate(route.waypoints[:-1]):
        expected = now + i * step
        assert wp.timestamp == expected, f"Waypoint {i}: expected {expected}, got {wp.timestamp}"
```

### Learnings des stories précédentes

**Story 2.1 (tidal) :**
- `export PATH="$HOME/.local/bin:$PATH"` avant toute commande poetry
- `make` non installé — utiliser `poetry run pytest` et `poetry run ruff check` directement
- Ligne vide obligatoire entre groupes d'imports (ruff I001) : stdlib / third-party / first-party

**Story 1.3 (protocols) :**
- `@runtime_checkable` vérifie uniquement l'existence du nom de méthode — pas besoin d'en faire plus pour les mocks ; une classe simple sans décorateur suffit tant qu'elle implémente `get_current` / `intersects_land`

**Deferred work à traiter dans cette story :**
- "Heading/direction fields acceptent valeurs hors [0, 360) — normalisation = module routing (Story 2.2)" → normaliser `fwd_az % 360.0` et `cog % 360.0` systématiquement

### Fichiers à créer / modifier

| Action | Fichier |
|--------|---------|
| Remplacer stub | `voyageur/routing/planner.py` |
| Ajouter fixtures | `tests/conftest.py` (append only) |
| Créer | `tests/test_routing.py` |

### Fichiers à NE PAS toucher

- `voyageur/models.py` — complet, ne pas modifier
- `voyageur/tidal/protocol.py` — complet, ne pas modifier
- `voyageur/cartography/protocol.py` — complet, ne pas modifier
- `voyageur/tidal/impl.py` — complet, ne pas modifier
- `voyageur/routing/safety.py` — stub pour Story 3.2, ne pas modifier
- `voyageur/cli/main.py` — stub pour Story 2.4, ne pas modifier
- `voyageur/output/formatter.py` — stub pour Story 2.3, ne pas modifier

### Project Structure Notes

- `voyageur/routing/planner.py` est le seul fichier routing à implémenter dans cette story
- `routing/` n'importe jamais de `tidal/impl.py` ni de `cartography/impl.py` — uniquement les protocols
- `tests/test_routing.py` n'importe jamais depuis `voyageur.tidal.impl` directement

### References

- Architecture : `_bmad-output/planning-artifacts/architecture.md#Routing Algorithm` — algorithme direct propagation
- Architecture : `_bmad-output/planning-artifacts/architecture.md#Module Interface Contracts` — dependency injection via Protocol
- Architecture : `_bmad-output/planning-artifacts/architecture.md#Naming Patterns` — snake_case, PascalCase, UPPER_SNAKE
- Project context : `_bmad-output/planning-artifacts/project-context.md#Critical Don't-Miss Rules` — edge cases
- Deferred work : `_bmad-output/implementation-artifacts/deferred-work.md` — heading normalization (Story 2.2)
- Story 2.1 : `_bmad-output/implementation-artifacts/2-1-harmonic-tidal-model.md#Dev Notes` — patterns pyproj, ruff, imports

## Review Findings

- [x] [Review][Patch] Add test with non-zero tidal current verifying SOG is affected by tide [tests/test_routing.py]
- [x] [Review][Patch] Fix `westerly_wind` fixture docstring: 240° is SW (southwest), not west [tests/test_routing.py]
- [x] [Review][Patch] Fix test bound in `test_zero_wind_zero_current_does_not_raise`: `MAX_STEPS + 2` → `MAX_STEPS` [tests/test_routing.py]
- [x] [Review][Defer] 2000 duplicate waypoints when SOG=0 (in irons + zero tide) — deferred, by design per AC4; MAX_STEPS is the specified safety limit [voyageur/routing/planner.py]
- [x] [Review][Defer] No completion signal to distinguish truncated route from successful arrival — deferred, Route model change outside story scope; deferred to output/CLI layer
- [x] [Review][Defer] `step_minutes=0` or negative not validated — deferred, pre-existing; input validation = Story 2.4 per deferred-work.md
- [x] [Review][Defer] Final arrival waypoint records stale `heading` and `sog` from previous step — deferred, cosmetic for MVP
- [x] [Review][Defer] `test_waypoint_timestamps_increment` skips final arrival waypoint timestamp — deferred, minor coverage gap
- [x] [Review][Defer] Naive `departure_time` silently accepted — deferred, pre-existing; tracked in deferred-work.md
- [x] [Review][Defer] Negative `wind.speed` or `current_speed` not validated — deferred, pre-existing; tracked in deferred-work.md
- [x] [Review][Defer] `CartographyProvider.intersects_land()` never called in propagation loop — deferred, intentional; Story 3.1

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `voyageur/routing/planner.py` : `RoutePlanner` avec propagation directe — addition vectorielle vent + tidal, modèle polaire simplifié (fraction TWA), avancement pyproj Geod.fwd(), terminaison à 500 m de la destination ou MAX_STEPS
- `tests/conftest.py` : ajout `_ZeroTidalProvider`, `_NoObstacleCartographyProvider`, fixtures `mock_tidal` et `mock_cartography`
- `tests/test_routing.py` : 10 tests — happy path Cherbourg→Granville, validité waypoints, timestamps incrémentaux, durée positive, origine=destination, vent nul sans exception, step=1min, NFR1 performance Cherbourg→Le Havre
- 30/30 tests passent (0 régression), ruff 0 violations, NFR1 : 0.16s << 5s
- Deferred work traité : heading normalisé via `fwd_az % 360.0` (cf. deferred-work.md Story 1.2)

### File List

- `voyageur/routing/planner.py`
- `tests/conftest.py`
- `tests/test_routing.py`
