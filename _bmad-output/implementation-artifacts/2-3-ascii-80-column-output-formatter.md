# Story 2.3: ASCII 80-Column Output Formatter

Status: done

## Story

As JC,
I want the route computation results displayed as a structured ASCII table that fits an 80-column terminal,
So that I can read my passage plan clearly without wrapping or truncation.

## Acceptance Criteria

1. `format_timeline(route, wind=None)` returns a string with a header row and one data row per waypoint
2. Each row contains: elapsed time (HH:MM), position (lat/lon), heading (°), SOG (kn), tidal current (dir/spd), wind (dir/spd)
3. Every row is ≤ 80 characters wide
4. A summary section follows the table: total distance (NM), estimated duration, count of decision-point flags
5. `tests/test_output.py` passes: 80-col constraint verified on a sample route of at least 20 steps
6. `poetry run ruff check voyageur/ tests/` reports zero violations

## Tasks / Subtasks

- [x] Implémenter `voyageur/output/formatter.py` (AC: 1, 2, 3, 4)
  - [x] Constante module-level `_GEOD` pour calcul de distance
  - [x] Helpers privés : `_elapsed`, `_fmt_lat`, `_fmt_lon`, `_fmt_hdg`, `_fmt_sog`, `_fmt_dir_spd`
  - [x] Fonction publique `format_timeline(route: Route, wind: WindCondition | None = None) -> str`
  - [x] Ligne de séparation `─` × 78 (tient dans 80 cols avec LF)
  - [x] Ligne de résumé : distance NM (somme géodésique), durée (Xh Ym), flags=0

- [x] Créer `tests/test_output.py` (AC: 5)
  - [x] Fixture `sample_route` : route Cherbourg→Granville ≥ 20 waypoints via `RoutePlanner`
  - [x] Test contrainte 80 cols : chaque ligne du retour ≤ 80 chars
  - [x] Test headers présents : "TIME", "LAT", "LON", "HDG", "SOG" dans la sortie
  - [x] Test résumé : "NM" et "Duration" présents dans la sortie
  - [x] Test route vide (0 waypoints) : retourne une chaîne (pas d'exception)

- [x] Valider (AC: 6)
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run ruff check voyageur/ tests/`
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run pytest tests/ -v`

### Review Findings

- [x] [Review][Defer] `_fmt_duration` division float avant truncation [voyageur/output/formatter.py:68] — deferred, cosmétique
- [x] [Review][Defer] `_fmt_dir_spd` colonne WIND = 7 chars pour speed < 10 kn [voyageur/output/formatter.py:52] — deferred, désalignement visuel mineur, contrainte 80 cols respectée
- [x] [Review][Defer] `_fmt_sog` overflow théorique pour SOG ≥ 100 kn [voyageur/output/formatter.py:48] — deferred, impossible en voilier

## Dev Notes

### Fichier cible : `voyageur/output/formatter.py`

Ce fichier est actuellement un stub. Le remplacer entièrement.

### Décision de design : données tidal/vent non portées par Waypoint

`Waypoint` ne contient pas `TidalState`. `Route` ne stocke pas de conditions vent.
- Colonne TIDE → afficher `---/---` (placeholder MVP — donnée non disponible sans extension de Route)
- Colonne WIND → provient du paramètre `wind: WindCondition | None` ; si `None` → `---/---`

Ce choix est documenté dans le schéma d'architecture :
> "Route (list of Waypoints + TidalState + WindCondition per step)"
L'extension de `Route` pour porter les données tidal par step est déferrée à la couche CLI (Story 2.4).

### Signature exacte

```python
def format_timeline(route: Route, wind: WindCondition | None = None) -> str:
    """Format a computed route as an 80-column ASCII timeline table."""
```

### Largeurs de colonnes (CRITIQUE pour la contrainte NFR3)

```
Colonne  Format string              Exemple       Largeur
TIME     f"{h:02d}:{m:02d}"         "08:15"           5
LAT      f"{abs(lat):6.3f}{hem}"    "49.645N"          7
LON      f"{abs(lon):7.3f}{hem}"    "  1.622W"         8
HDG      f"{int(hdg):3d}°"          "180°"             4
SOG      f"{sog:4.1f}kn"            " 6.8kn"           6
TIDE     "---/---"                  "---/---"           7
WIND     f"{dir:3.0f}/{spd:.1f}"    "240/15.0"         8
```

Séparateur entre colonnes : `"  "` (2 espaces).

Largeur max d'une ligne de données :
`5 + 2 + 7 + 2 + 8 + 2 + 4 + 2 + 6 + 2 + 7 + 2 + 8 = 57 chars` — largement sous 80.

La ligne de séparation `"─" * 57` (ou un tiret simple `"-" * 57`) tient dans 80 cols.

> **NE PAS utiliser** `"─" * 80` : le caractère U+2500 est multi-octet ; `len()` donne 80 mais le terminal peut le traiter comme 2 colonnes. Utiliser `"-"` (ASCII) ou vérifier avec `len()` et non largeur terminale.

Utiliser `"-" * 57` pour la ligne de séparation.

### Calcul de l'élapsed

```python
def _elapsed(wp_timestamp: datetime.datetime, departure_time: datetime.datetime) -> str:
    """Return elapsed time as HH:MM."""
    total_sec = int((wp_timestamp - departure_time).total_seconds())
    h, rem = divmod(total_sec, 3600)
    m = rem // 60
    return f"{h:02d}:{m:02d}"
```

### Format lat/lon

```python
def _fmt_lat(lat: float) -> str:
    """Format latitude as NNN.NNNx (7 chars)."""
    hem = "N" if lat >= 0.0 else "S"
    return f"{abs(lat):6.3f}{hem}"


def _fmt_lon(lon: float) -> str:
    """Format longitude as NNN.NNNx (8 chars)."""
    hem = "E" if lon >= 0.0 else "W"
    return f"{abs(lon):7.3f}{hem}"
```

### Calcul de la distance totale

Sommer les distances géodésiques entre waypoints consécutifs via `_GEOD.inv()`. Convertir mètres → miles nautiques : `1 NM = 1852 m`.

```python
_GEOD: Geod = Geod(ellps="WGS84")

def _total_distance_nm(waypoints: list[Waypoint]) -> float:
    """Compute total route distance in nautical miles."""
    if len(waypoints) < 2:
        return 0.0
    total_m = 0.0
    for a, b in zip(waypoints[:-1], waypoints[1:]):
        _, _, dist_m = _GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        total_m += dist_m
    return total_m / 1852.0
```

Note : `_GEOD.inv(lon1, lat1, lon2, lat2)` — **longitude en premier** (convention pyproj, identique à Story 2.1 et 2.2).

### Format de la durée

```python
def _fmt_duration(td: datetime.timedelta) -> str:
    """Format timedelta as 'Xh Ym'."""
    total_min = int(td.total_seconds() / 60)
    h, m = divmod(total_min, 60)
    return f"{h}h {m:02d}m"
```

### Structure de `format_timeline`

```python
SEP = "  "
HEADER = SEP.join(["TIME ", "LAT    ", "LON      ", "HDG ", "SOG   ", "TIDE   ", "WIND   "])
DIVIDER = "-" * len(HEADER)

lines: list[str] = [HEADER, DIVIDER]
for wp in route.waypoints:
    row = SEP.join([elapsed, lat, lon, hdg, sog, tide, wind_col])
    lines.append(row)
lines.append(DIVIDER)

# Summary
dist_nm = _total_distance_nm(route.waypoints)
duration_str = _fmt_duration(route.total_duration)
lines.append(f"Total: {dist_nm:.1f} NM  |  Duration: {duration_str}  |  Flags: 0")
return "\n".join(lines)
```

> **ATTENTION** : calculer `HEADER` une seule fois en dehors de la boucle.
> Vérifier que `len(DIVIDER) <= 78` (78 + "\n" = 79 < 80). Si besoin, ajuster.

### Imports ruff-conformes

```python
import datetime    # stdlib
                   # ← ligne vide
from pyproj import Geod   # third-party
                   # ← ligne vide
from voyageur.models import Route, Waypoint, WindCondition  # first-party
```

Ne pas importer `BoatProfile` ni `TidalState` — non utilisés dans ce module.

### Fixture `sample_route` pour tests

Générer une route réelle via `RoutePlanner` (garantit ≥ 20 waypoints sur Cherbourg→Granville) :

```python
@pytest.fixture
def sample_route(mock_tidal, mock_cartography, now) -> Route:
    """Route Cherbourg→Granville with at least 20 waypoints."""
    from voyageur.models import BoatProfile, WindCondition
    from voyageur.routing.planner import RoutePlanner

    boat = BoatProfile(name="Test", loa=12.0, draft=1.8, sail_area=65.0, default_step=15)
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    planner = RoutePlanner(tidal=mock_tidal, cartography=mock_cartography)
    route = planner.compute(
        origin=(49.6453, -1.6222),   # Cherbourg
        destination=(48.8327, -1.5971),  # Granville
        departure_time=now,
        wind=wind,
        boat=boat,
        step_minutes=15,
    )
    assert len(route.waypoints) >= 20, "Fixture must produce ≥20 waypoints"
    return route
```

La fixture utilise les fixtures `mock_tidal`, `mock_cartography`, `now` — déjà définies dans `conftest.py`.

### Test contrainte 80 colonnes

```python
def test_80_col_constraint(sample_route, now):
    from voyageur.models import WindCondition
    wind = WindCondition(timestamp=now, direction=240.0, speed=15.0)
    output = format_timeline(sample_route, wind=wind)
    for i, line in enumerate(output.splitlines()):
        assert len(line) <= 80, f"Line {i} exceeds 80 cols ({len(line)}): {line!r}"
```

### Learnings des stories précédentes

**Story 2.2 :**
- `export PATH="$HOME/.local/bin:$PATH"` avant toute commande poetry
- `_GEOD.inv(lon1, lat1, lon2, lat2)` — longitude PREMIER
- ruff I001 : ligne vide obligatoire entre groupes d'imports

**Story 2.1/2.2 :**
- Utiliser `_GEOD` au niveau module (pas dans `__init__`), stateless, réutilisable

### Fichiers à créer

| Action | Fichier |
|--------|---------|
| Remplacer stub | `voyageur/output/formatter.py` |
| Créer | `tests/test_output.py` |

### Fichiers à NE PAS toucher

- `voyageur/models.py` — ne pas modifier (tidal/wind par step = Story 2.4+)
- `voyageur/routing/planner.py` — complet
- `tests/conftest.py` — ne pas modifier (fixtures existantes suffisent)
- `voyageur/output/__init__.py` — stub vide, laisser tel quel

### Project Structure Notes

- `voyageur/output/formatter.py` expose **une seule fonction publique** : `format_timeline`
- `output/` n'importe jamais depuis `routing/`, `tidal/`, ou `cartography/` — uniquement `models` et pyproj
- `tests/test_output.py` importe depuis `voyageur.output.formatter` et `voyageur.routing.planner` (pour la fixture)

### References

- Architecture : `_bmad-output/planning-artifacts/architecture.md#Format Patterns` — 80-col, séparateur 2 espaces, HH:MM
- Architecture : `_bmad-output/planning-artifacts/architecture.md#Module Boundaries` — output dépend de models uniquement
- Project context : `_bmad-output/planning-artifacts/project-context.md#Critical Don't-Miss Rules` — `print()` interdit, utiliser `typer.echo()` en CLI (mais le formatter retourne une string, pas d'echo direct)
- Story 2.2 : `_bmad-output/implementation-artifacts/2-2-direct-route-propagation-algorithm.md` — Waypoint fields, RoutePlanner API, fixtures conftest

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implémenté `format_timeline(route, wind=None)` dans `voyageur/output/formatter.py`
- Colonnes : TIME(5) LAT(7) LON(8) HDG(4) SOG(6) TIDE(7) WIND(8), séparateur 2 espaces → 57 chars max/ligne
- HEADER calculé dynamiquement ; DIVIDER = `"-" * len(HEADER)` = 57 chars (≤ 78 ✓)
- Colonne TIDE : `"---/---"` (placeholder MVP — Waypoint ne porte pas TidalState)
- Colonne WIND : `_fmt_dir_spd(wind.direction, wind.speed)` si wind fourni, sinon `"---/---"`
- Distance totale via `_GEOD.inv(lon1, lat1, lon2, lat2)` (longitude premier, convention pyproj)
- 5 tests dans `tests/test_output.py` : 80-col, headers, résumé, route vide, wind=None
- 36 tests passent, 0 régression, ruff: 0 violation

### File List

- `voyageur/output/formatter.py` — remplacé (stub → implémentation complète)
- `tests/test_output.py` — créé
