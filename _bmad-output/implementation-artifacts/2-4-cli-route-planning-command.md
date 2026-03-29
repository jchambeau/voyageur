# Story 2.4: CLI Route Planning Command

Status: done

## Story

As JC,
I want to run `voyageur --from Cherbourg --to Granville --depart 2026-03-29T08:00 --wind 240/15` and see the full route timeline,
So that I can plan a coastal passage from my terminal in seconds.

## Acceptance Criteria

1. `voyageur --from PORT --to PORT --depart ISO8601 --wind DIR/SPD` prints the route timeline to stdout and exits 0
2. Port names resolve to coordinates for at least: Cherbourg, Granville, Le Havre, Saint-Malo, Barfleur, Saint-Vaast-la-Hougue, Honfleur (case-insensitive)
3. `--from` and `--to` also accept `latN/lonW` coordinates (e.g., `49.65N/1.62W`)
4. `--step` flag sets time step in minutes (1, 5, 15, 30, 60); default is 15
5. If `~/.voyageur/boat.yaml` exists it is loaded automatically; if absent a default BoatProfile is used with a `⚠` notice on stderr
6. Unknown port or invalid wind format → stderr `✗` message + exit code 1
7. `tests/test_cli.py` passes: happy-path Cherbourg→Granville invocation + invalid-port error case
8. `poetry run ruff check voyageur/ tests/` reports zero violations

## Tasks / Subtasks

- [x] Implémenter `voyageur/cli/main.py` (AC: 1, 2, 3, 4, 5, 6)
  - [x] Table `PORTS` : dict case-insensitive → (lat, lon) pour les 7 ports requis
  - [x] Helpers privés : `_parse_position`, `_parse_wind`, `_parse_depart`, `_load_boat`
  - [x] `_StubCartography` : implémentation CartographyProvider → retourne toujours False
  - [x] Implémenter le corps de `plan()` : parse inputs → RoutePlanner.compute() → format_timeline() → typer.echo()
  - [x] Gestion d'erreur : port inconnu + format wind invalide → typer.echo(err=True) + raise typer.Exit(1)

- [x] Créer `tests/test_cli.py` (AC: 7)
  - [x] Fixture `runner` : typer.testing.CliRunner
  - [x] `test_plan_cherbourg_granville` : happy path, exit 0, "NM" dans output
  - [x] `test_plan_invalid_port` : port inconnu, exit 1, stderr contient "✗"

- [x] Valider (AC: 8)
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run ruff check voyageur/ tests/`
  - [x] `export PATH="$HOME/.local/bin:$PATH" && poetry run pytest tests/ -v`

### Review Findings

- [x] [Review][Patch] `_load_boat` plante sur YAML incomplet/vide/illisible [voyageur/cli/main.py:86-93] — KeyError sur champ manquant, AttributeError si safe_load retourne None, OSError/YAMLError non capturés
- [x] [Review][Defer] `--step` non validé contre {1,5,15,30,60} [voyageur/cli/main.py:105] — deferred, hors scope spec MVP
- [x] [Review][Defer] `_parse_wind` direction ≥ 360 non rejetée [voyageur/cli/main.py:26] — deferred, planner normalise avec % 360
- [x] [Review][Defer] `_parse_position` coordonnées hors limites acceptées (lat>90, lon>180) [voyageur/cli/main.py:25] — deferred, hors scope spec
- [x] [Review][Defer] Tests manquants pour lat/lon, step invalide, boat.yaml absent/malformé [tests/test_cli.py] — deferred, spec requiert 2 tests minimaux

## Dev Notes

### Fichier cible : `voyageur/cli/main.py`

Le stub actuel a déjà la signature `plan()` avec les bons paramètres Typer. **Remplacer uniquement le corps de la fonction** (et ajouter les helpers + imports manquants). Ne pas modifier la signature Typer ni le nom du paramètre `from_port`.

### Stub CartographyProvider dans main.py

Story 3.1 n'étant pas encore implémentée, le CLI utilise un stub local qui retourne toujours `False` pour `intersects_land`. Définir directement dans `main.py` :

```python
class _StubCartography:
    """No-obstacle stub — replaced in Story 3.1 by GeoJsonCartography."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        """Always return False — obstacle detection deferred to Story 3.1."""
        return False
```

> **Ne pas** créer ce stub dans `voyageur/cartography/` — il est temporaire et privé au CLI.

### Table des ports (CRITIQUE : 7 ports requis par AC2)

```python
PORTS: dict[str, tuple[float, float]] = {
    "cherbourg":              (49.6453, -1.6222),
    "granville":              (48.8327, -1.5971),
    "le havre":               (49.4892,  0.1080),
    "saint-malo":             (48.6490, -1.9800),
    "barfleur":               (49.6733, -1.2638),
    "saint-vaast-la-hougue":  (49.5875, -1.2703),
    "honfleur":               (49.4189,  0.2337),
}
```

La recherche est **case-insensitive** : `name.strip().lower()` avant lookup. Alias optionnel : `"st-malo"` → `"saint-malo"`.

### Format lat/lon accepté (AC3)

Format : `"49.65N/1.62W"` — regex : `^(\d+\.?\d*)([NS])/(\d+\.?\d*)([EW])$`

```python
import re

_LATLON_RE = re.compile(
    r"^(\d+\.?\d*)([NS])/(\d+\.?\d*)([EW])$", re.IGNORECASE
)

def _parse_position(s: str) -> tuple[float, float] | None:
    """Parse port name or latN/lonW string. Returns (lat, lon) or None."""
    key = s.strip().lower()
    if key in PORTS:
        return PORTS[key]
    m = _LATLON_RE.match(s.strip())
    if m:
        lat = float(m.group(1)) * (1 if m.group(2).upper() == "N" else -1)
        lon = float(m.group(3)) * (1 if m.group(4).upper() == "E" else -1)
        return lat, lon
    return None
```

### Parsing du vent (AC6)

Regex : `^\d{1,3}/\d+(\.\d+)?$`

```python
_WIND_RE = re.compile(r"^\d{1,3}/\d+(\.\d+)?$")

def _parse_wind(
    s: str, timestamp: datetime.datetime
) -> WindCondition | None:
    """Parse 'DIR/SPD' string. Returns WindCondition or None."""
    if not _WIND_RE.match(s.strip()):
        return None
    parts = s.strip().split("/")
    return WindCondition(
        timestamp=timestamp,
        direction=float(parts[0]),
        speed=float(parts[1]),
    )
```

### Parsing de la date de départ

`datetime.fromisoformat()` retourne un datetime naïf si pas de timezone. Forcer UTC :

```python
def _parse_depart(s: str) -> datetime.datetime | None:
    """Parse ISO 8601 string to UTC-aware datetime. Returns None on parse error."""
    try:
        dt = datetime.datetime.fromisoformat(s.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError:
        return None
```

### Chargement du profil bateau (AC5)

Chemin : `pathlib.Path.home() / ".voyageur" / "boat.yaml"`. Ne jamais hardcoder de chemin absolu.

```python
_DEFAULT_BOAT = BoatProfile(
    name="Default", loa=12.0, draft=1.8, sail_area=65.0, default_step=15
)

def _load_boat() -> tuple[BoatProfile, bool]:
    """Load boat profile from ~/.voyageur/boat.yaml. Returns (profile, loaded)."""
    import pathlib

    import yaml as _yaml

    path = pathlib.Path.home() / ".voyageur" / "boat.yaml"
    if not path.exists():
        return _DEFAULT_BOAT, False
    data = _yaml.safe_load(path.read_text(encoding="utf-8"))
    return (
        BoatProfile(
            name=data.get("name", "Default"),
            loa=float(data["loa"]),
            draft=float(data["draft"]),
            sail_area=float(data["sail_area"]),
            default_step=int(data.get("default_step", 15)),
        ),
        True,
    )
```

### Corps de `plan()` — flux complet

```python
def plan(...) -> None:
    """Plan a sailing passage between two Norman coast ports."""
    # 1. Parse departure time
    departure_time = _parse_depart(depart)
    if departure_time is None:
        typer.echo(f"✗ Invalid departure time: {depart!r}", err=True)
        raise typer.Exit(1)

    # 2. Parse positions
    origin = _parse_position(from_port)
    if origin is None:
        typer.echo(f"✗ Unknown port or invalid position: {from_port!r}", err=True)
        raise typer.Exit(1)
    destination = _parse_position(to_port)
    if destination is None:
        typer.echo(f"✗ Unknown port or invalid position: {to_port!r}", err=True)
        raise typer.Exit(1)

    # 3. Parse wind
    wind_condition = _parse_wind(wind, departure_time)
    if wind_condition is None:
        typer.echo(f"✗ Invalid wind format: {wind!r}. Expected DIR/SPD (e.g. 240/15)", err=True)
        raise typer.Exit(1)

    # 4. Load boat profile
    boat, loaded = _load_boat()
    if not loaded:
        typer.echo(
            "⚠ No boat profile found at ~/.voyageur/boat.yaml — using defaults.",
            err=True,
        )

    # 5. Compute route
    from voyageur.routing.planner import RoutePlanner
    from voyageur.tidal.impl import HarmonicTidalModel

    planner = RoutePlanner(tidal=HarmonicTidalModel(), cartography=_StubCartography())
    route = planner.compute(
        origin=origin,
        destination=destination,
        departure_time=departure_time,
        wind=wind_condition,
        boat=boat,
        step_minutes=step,
    )

    # 6. Format and display
    from voyageur.output.formatter import format_timeline

    typer.echo(format_timeline(route, wind=wind_condition))
```

> **CRITIQUE** : imports `RoutePlanner`, `HarmonicTidalModel`, `format_timeline` dans le corps de `plan()` (lazy imports) afin d'éviter les imports circulaires et de garder le temps de démarrage du CLI minimal pour les commandes comme `--help`.

### Imports ruff-conformes pour main.py

```python
import datetime
import re

import typer

from voyageur.models import BoatProfile, Route, Waypoint, WindCondition
```

Note : `Route` est importé uniquement si nécessaire pour le type du stub `_StubCartography`. Sinon omettre.

### Tests CLI avec CliRunner

```python
from typer.testing import CliRunner
from voyageur.cli.main import app

runner = CliRunner()

def test_plan_cherbourg_granville():
    result = runner.invoke(app, [
        "--from", "Cherbourg",
        "--to", "Granville",
        "--depart", "2026-03-29T08:00",
        "--wind", "240/15",
    ])
    assert result.exit_code == 0
    assert "NM" in result.output


def test_plan_invalid_port():
    result = runner.invoke(app, [
        "--from", "PortInconnu",
        "--to", "Granville",
        "--depart", "2026-03-29T08:00",
        "--wind", "240/15",
    ])
    assert result.exit_code == 1
```

> **Note** : `CliRunner` de Typer capture stdout ET stderr dans `result.output`. Pour tester stderr séparément, utiliser `mix_stderr=False` : `CliRunner(mix_stderr=False)` — `result.stderr` contient le stderr séparé.

### Structure du test stderr

```python
def test_plan_invalid_port():
    runner_sep = CliRunner(mix_stderr=False)
    result = runner_sep.invoke(app, [
        "--from", "PortInconnu",
        "--to", "Granville",
        "--depart", "2026-03-29T08:00",
        "--wind", "240/15",
    ])
    assert result.exit_code == 1
    assert "✗" in result.stderr
```

### Fichiers à modifier / créer

| Action | Fichier |
|--------|---------|
| Modifier stub | `voyageur/cli/main.py` |
| Créer | `tests/test_cli.py` |

### Fichiers à NE PAS toucher

- `voyageur/models.py` — ne pas modifier
- `voyageur/routing/planner.py` — ne pas modifier
- `voyageur/tidal/impl.py` — ne pas modifier
- `voyageur/output/formatter.py` — ne pas modifier
- `tests/conftest.py` — ne pas modifier
- `voyageur/cli/config.py` — stub Story 3.3, ne pas toucher
- `voyageur/cartography/` — Story 3.1, ne pas toucher

### Learnings des stories précédentes

**Story 2.3 :**
- `export PATH="$HOME/.local/bin:$PATH"` avant toute commande poetry
- ruff I001 : ligne vide obligatoire entre groupes d'imports
- ruff E501 : max 88 chars par ligne — wrapping multi-ligne pour les longues chaînes

**Story 2.1/2.2 :**
- `_GEOD.inv(lon1, lat1, lon2, lat2)` — longitude PREMIER (non applicable ici, mais à garder en tête)
- Constantes module-level en `UPPER_SNAKE_CASE`

**Projet (project-context.md) :**
- `print()` est **interdit** — toujours `typer.echo()`
- `typer.echo(msg, err=True)` + `raise typer.Exit(1)` pour les erreurs — jamais `sys.exit()`
- `pathlib.Path.home() / ".voyageur"` — jamais de chemin absolu hardcodé
- `datetime.now(timezone.utc)` — jamais `datetime.now()` naïf
- `HarmonicTidalModel` s'instancie sans arguments : `HarmonicTidalModel()`

### Piège : `--from` est un mot-clé Python

Typer accepte `from_port: str = typer.Option(..., "--from", ...)` — le paramètre Python s'appelle `from_port` mais le flag CLI est `--from`. Le stub actuel l'a déjà correctement. **Ne pas renommer ce paramètre.**

### Piège : Typer et exit codes

`raise typer.Exit(1)` provoque exit code 1. `raise typer.Exit(0)` ou fin normale = exit code 0. Ne jamais utiliser `sys.exit()`.

### References

- Architecture : `_bmad-output/planning-artifacts/architecture.md#Framework-Specific Rules (Typer CLI)`
- project-context : `_bmad-output/planning-artifacts/project-context.md#Critical Don't-Miss Rules`
- Story 2.2 : `_bmad-output/implementation-artifacts/2-2-direct-route-propagation-algorithm.md` — RoutePlanner API
- Story 2.3 : `_bmad-output/implementation-artifacts/2-3-ascii-80-column-output-formatter.md` — format_timeline API

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implémenté `voyageur/cli/main.py` : helpers `_parse_position`, `_parse_wind`, `_parse_depart`, `_load_boat` + corps de `plan()`
- Table `PORTS` : 7 ports requis + alias `st-malo` ; lookup case-insensitive via `.strip().lower()`
- Format lat/lon : regex `^(\d+\.?\d*)([NS])/(\d+\.?\d*)([EW])$` avec signe hémisphère
- `_StubCartography` (local à main.py) : intersects_land → False toujours
- `HarmonicTidalModel` + `RoutePlanner` + `format_timeline` importés en lazy imports dans `plan()`
- Boat profile : `~/.voyageur/boat.yaml` via pathlib.Path.home() ; défaut + notice stderr si absent
- Corrigé : Typer 0.24.1 ne supporte pas `mix_stderr=False` → tests utilisent `result.output`
- 38 tests passent, 0 régression, ruff: 0 violation

### File List

- `voyageur/cli/main.py` — remplacé (stub → implémentation complète)
- `tests/test_cli.py` — créé
