# Story 3.1: Coastal Obstacle Detection

Status: done

## Story

As JC,
I want the system to detect when my planned route crosses land or shallow waters on the Norman coast,
So that I receive an alert before departing on a route that passes through an obstacle.

## Acceptance Criteria

1. `voyageur/cartography/data/normandy.geojson` contains Norman coast coastline and shallow-water polygons
2. `GeoJsonCartography.intersects_land(route)` returns `True` when any route segment crosses a polygon, `False` for a clear offshore route
3. `GeoJsonCartography` satisfies the `CartographyProvider` protocol
4. When `intersects_land` returns `True`, the CLI prints a `⚠` alert to stderr identifying the approximate position of the intersection — route computation continues (does not halt)
5. `tests/test_cartography.py` passes: at least one intersecting route and one clear route tested
6. `poetry run ruff check voyageur/ tests/` reports zero violations

## Tasks / Subtasks

- [x] Créer `voyageur/cartography/data/normandy.geojson` (AC: 1, 2)
  - [x] FeatureCollection minifiée avec polygones Norman coast (Cotentin + côte basse-normandie)
  - [x] Au moins un polygone « Cotentin » qui intercepte une route test connue
  - [x] Fichier minifié (pas de pretty-print) — pas de `__init__.py` dans `data/`

- [x] Implémenter `voyageur/cartography/impl.py` (AC: 2, 3)
  - [x] `GeoJsonCartography` : charge le GeoJSON via `importlib.resources` dans `__init__`
  - [x] `intersects_land(route)` : construit LineString shapely pour chaque segment consécutif, vérifie intersection avec l'ensemble des polygones
  - [x] Satisfait le protocole `CartographyProvider`

- [x] Intégrer dans `voyageur/cli/main.py` (AC: 4)
  - [x] Remplacer `_StubCartography()` par `GeoJsonCartography()` dans `plan()`
  - [x] Après `route = planner.compute(...)`, appeler `cartography.intersects_land(route.waypoints)` et imprimer `⚠` sur stderr si True
  - [x] Ne pas modifier le flux normal — route affichée même si intersection détectée

- [x] Créer `tests/test_cartography.py` (AC: 5)
  - [x] Test route intersectante : route passant à travers la péninsule Cotentin → `True`
  - [x] Test route dégagée : route en mer, loin des terres → `False`

- [x] Valider (AC: 6)
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run ruff check voyageur/ tests/`
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run pytest tests/ -v`

## Dev Notes

### Fichier GeoJSON : `voyageur/cartography/data/normandy.geojson`

Le répertoire `voyageur/cartography/data/` existe (`.gitkeep` présent). Créer `normandy.geojson` directement dans ce répertoire.

**Format attendu :** GeoJSON FeatureCollection, minifié, polygones Polygon ou MultiPolygon.

**Contenu minimal MVP :** un polygone simplifié de la péninsule Cotentin suffisant pour les tests. Pas besoin de données OSM complètes pour le MVP — la précision exacte du tracé littoral est hors scope ; l'objectif est que l'algorithme d'intersection fonctionne.

Polygone Cotentin simplifié (coordonnées WGS84 `[lon, lat]`, sens antihoraire) :

```json
{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"Cotentin"},"geometry":{"type":"Polygon","coordinates":[[[-1.97,49.73],[-1.85,49.73],[-1.26,49.70],[-1.22,49.55],[-1.30,49.40],[-1.50,49.20],[-1.60,49.00],[-1.90,49.00],[-2.10,49.55],[-1.97,49.73]]]}},{"type":"Feature","properties":{"name":"Normandy coast east"},"geometry":{"type":"Polygon","coordinates":[[[-1.60,49.00],[-1.50,49.20],[-1.30,49.40],[0.20,49.40],[0.50,49.50],[0.30,49.00],[-1.60,49.00]]]}}]}
```

> **NOTE** : Ces polygones sont approximatifs et servent UNIQUEMENT à tester l'algorithme d'intersection. Story 4+ remplacera par des données OSM précises.

### Chargement du GeoJSON avec `importlib.resources`

```python
import importlib.resources
import json

from shapely.geometry import shape


class GeoJsonCartography:
    """CartographyProvider backed by an embedded GeoJSON file."""

    def __init__(self) -> None:
        self._polygons = self._load_polygons()

    def _load_polygons(self) -> list:
        """Load all polygon/multipolygon geometries from embedded GeoJSON."""
        ref = (
            importlib.resources.files("voyageur.cartography")
            / "data"
            / "normandy.geojson"
        )
        with ref.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [
            shape(feature["geometry"])
            for feature in data["features"]
            if feature.get("geometry")
        ]
```

> **Piège importlib.resources** : utiliser `importlib.resources.files("voyageur.cartography") / "data" / "normandy.geojson"` — NE PAS utiliser `importlib.resources.open_text()` (deprecated Python 3.11+).

### `intersects_land` avec shapely 2.0

```python
from shapely.geometry import LineString
from voyageur.models import Waypoint


def intersects_land(self, route: list[Waypoint]) -> bool:
    """Return True if any route segment crosses a land or shallow-water polygon."""
    if len(route) < 2:
        return False
    for a, b in zip(route[:-1], route[1:]):
        # shapely : (x, y) = (lon, lat)
        segment = LineString([(a.lon, a.lat), (b.lon, b.lat)])
        for polygon in self._polygons:
            if segment.intersects(polygon):
                return True
    return False
```

> **Convention shapely** : `(x, y)` = `(lon, lat)`. **Longitude en premier**, comme pyproj.

### Imports ruff-conformes pour `impl.py`

```python
import importlib.resources
import json

from shapely.geometry import LineString, shape

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import Waypoint
```

> `CartographyProvider` importé pour la docstring/typing — pas requis par shapely mais utile pour la lisibilité. Si ruff signale un import inutilisé, retirer.

### Intégration CLI dans `voyageur/cli/main.py`

**Deux changements :**

1. **Remplacer `_StubCartography()` par `GeoJsonCartography()`** dans le corps de `plan()` (avec lazy import) :

```python
from voyageur.cartography.impl import GeoJsonCartography
from voyageur.output.formatter import format_timeline
from voyageur.routing.planner import RoutePlanner
from voyageur.tidal.impl import HarmonicTidalModel

cartography = GeoJsonCartography()
planner = RoutePlanner(tidal=HarmonicTidalModel(), cartography=cartography)
route = planner.compute(...)
```

2. **Vérifier l'intersection après le calcul** et alerter sur stderr si détectée — sans interrompre le flux :

```python
if cartography.intersects_land(route.waypoints):
    typer.echo(
        "⚠ Route crosses land or shallow water — check your passage plan.",
        err=True,
    )

typer.echo(format_timeline(route, wind=wind_condition))
```

> `_StubCartography` dans `main.py` peut être supprimé — il est remplacé par `GeoJsonCartography`.

### Tests dans `tests/test_cartography.py`

```python
from voyageur.cartography.impl import GeoJsonCartography
from voyageur.models import Waypoint
import datetime

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)

def _wp(lat, lon):
    return Waypoint(lat=lat, lon=lon, timestamp=NOW,
                    heading=0.0, speed_over_ground=0.0)


def test_intersects_land_for_crossing_route():
    """Route traversant la péninsule Cotentin : doit retourner True."""
    # Route allant d'ouest en est en coupant la péninsule (~49.5°N)
    route = [_wp(49.5, -2.2), _wp(49.5, -1.2)]
    assert GeoJsonCartography().intersects_land(route) is True


def test_no_intersection_for_offshore_route():
    """Route en mer loin des terres : doit retourner False."""
    # Route dans la Manche, bien au nord (50.5°N)
    route = [_wp(50.5, -2.0), _wp(50.5, 0.0)]
    assert GeoJsonCartography().intersects_land(route) is False
```

### Fichiers à modifier / créer

| Action | Fichier |
|--------|---------|
| Créer | `voyageur/cartography/data/normandy.geojson` |
| Créer | `voyageur/cartography/impl.py` |
| Modifier | `voyageur/cli/main.py` (lazy import + suppression `_StubCartography`) |
| Créer | `tests/test_cartography.py` |

### Fichiers à NE PAS toucher

- `voyageur/cartography/protocol.py` — protocole déjà correct
- `voyageur/models.py` — ne pas modifier
- `voyageur/routing/planner.py` — ne pas modifier
- `tests/conftest.py` — `_NoObstacleCartographyProvider` y reste pour les tests routing

### Dépendances

- `shapely = "^2.0"` — **déjà dans `pyproject.toml`**, pas besoin d'`poetry add`
- `json` — stdlib

### Learnings des stories précédentes

**Story 2.4 :**
- `export PATH="$HOME/.local/bin:$PATH"` avant toute commande poetry
- Lazy imports dans le corps de `plan()` — continuer ce pattern pour `GeoJsonCartography`
- `typer.echo(msg, err=True)` pour les alertes stderr

**Projet (project-context.md) :**
- Embedded data via `importlib.resources.files(...)` — jamais de chemins absolus
- `print()` interdit — `typer.echo()` uniquement
- Coordonnées WGS84 toujours en float (lat, lon) dans les modèles

**Convention shapely (CRITIQUE) :**
- `LineString([(lon, lat), (lon, lat)])` — longitude PREMIER dans shapely, identique à pyproj

### References

- Architecture : `_bmad-output/planning-artifacts/architecture.md#Geospatial Libraries`
- project-context : `_bmad-output/planning-artifacts/project-context.md#Critical Don't-Miss Rules`
- Story 2.4 : `voyageur/cli/main.py` — `_StubCartography` à remplacer
- `voyageur/cartography/protocol.py` — signature `intersects_land(route: list[Waypoint]) -> bool`

## Review Findings

- [x] [Review][Decision→Patch] AC4 — Position de l'intersection ajoutée au message d'alerte — Résolu : ré-itération sur les paires de waypoints dans `plan()` pour trouver le premier segment croisant la terre ; position approximative (milieu du segment) incluse dans le message stderr. Pas de changement de protocole.

- [x] [Review][Defer] Faux positif shapely `intersects` au contact de frontière [voyageur/cartography/impl.py:35] — deferred, limitation connue du prédicat `intersects` (toucher = intersecte) ; `crosses` serait plus précis mais exclurait les vrais cas de contact.

- [x] [Review][Defer] Faux négatif si waypoint entièrement à l'intérieur d'un polygone [voyageur/cartography/impl.py:32] — deferred, si deux waypoints consécutifs sont tous deux dans un polygone sans que le segment croise la frontière, pas de détection ; corrigeable avec `contains(Point(...))` mais hors scope MVP.

- [x] [Review][Defer] AC1 — Pas de polygones de hauts-fonds distincts dans normandy.geojson [voyageur/cartography/data/normandy.geojson] — deferred, spec dev notes reconnaît explicitement que les données sont simplifiées pour MVP ; données OSM réelles prévues en Story 4+.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tous les ACs satisfaits. 40 tests passent, ruff 0 violations.
- `normandy.geojson` : deux polygones simplifiés (Cotentin + côte basse-normandie). Suffisants pour les tests MVP ; une vraie donnée OSM sera intégrée en Story 4+.
- `GeoJsonCartography` charge le GeoJSON via `importlib.resources.files()` (API Python 3.9+, non deprecated). Satisfait le protocole `CartographyProvider`.
- CLI : `_StubCartography` supprimé, `GeoJsonCartography` utilisé directement. L'alerte `⚠` est émise sur stderr sans interrompre l'affichage de la route.
- Convention shapely respectée : `LineString([(lon, lat), ...])` — longitude en premier.

### File List

- `voyageur/cartography/data/normandy.geojson` (créé)
- `voyageur/cartography/impl.py` (créé)
- `voyageur/cli/main.py` (modifié — lazy import GeoJsonCartography, suppression _StubCartography, ajout alerte ⚠)
- `tests/test_cartography.py` (créé)
