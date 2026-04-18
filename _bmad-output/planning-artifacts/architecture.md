---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: 'complete'
completedAt: '2026-03-28'
lastAmendedAt: '2026-04-15'
amendments:
  - date: '2026-04-15'
    section: 'GUI / Web Interface Architecture'
    summary: 'Added web-based GUI layer (FastAPI + Svelte + MapLibre) as new presentation layer; core protocols unchanged; CLI and ASCII formatter retained for export.'
inputDocuments: ['_bmad-output/planning-artifacts/prd.md']
workflowType: 'architecture'
project_name: 'voyageur'
user_name: 'JC'
date: '2026-03-28'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements — 31 FRs, 8 capability areas:**

| Capability Area | FRs | Phase |
|---|---|---|
| Route Planning | FR1–FR6 | MVP |
| Tidal Model | FR7–FR9 | MVP |
| Boat Profile Management | FR10–FR13 | MVP |
| Route Visualization & Output | FR14–FR16 | MVP |
| Condition Management | FR17–FR19 | MVP |
| Re-planning | FR20–FR22 | Growth |
| Multi-Criteria Routing | FR23–FR28 | Growth |
| External Data Integration | FR29–FR31 | Growth |

MVP scope: 19 FRs covering route computation, tidal simulation, boat profile persistence, and terminal display.

**Non-Functional Requirements — key architectural implications:**

- `NFR1/NFR2`: computation time constraints (< 5s at 15min step, < 30s at 1min step) — routing algorithm must be efficient from the start
- `NFR3`: 80-column terminal output — deterministic, constrained formatting
- `NFR4/NFR5`: documented module interfaces for `tidal` and `cartography` — module contracts are mandatory from day one
- `NFR6`: independent unit tests per module — strict dependency isolation required

**Scale & Complexity:**

- Primary domain: Python CLI / Geospatial
- Complexity: **Medium** — non-trivial algorithms (isochrone routing, harmonic tidal model) within a well-bounded technical scope
- No real-time features, no multi-tenancy, no regulatory compliance
- Estimated architectural components: 5 (`cli`, `routing`, `tidal`, `cartography`, `data-access`)

### Technical Constraints & Dependencies

- Standalone Python application — no server, no database
- Open data sources only: OpenSeaMap/OSM, SHOM open data
- No external API in MVP — all data is embedded or manually provided
- 80-column terminal output, human-readable YAML config
- Modular architecture enforced from MVP (NFR4/5/6)

### Cross-Cutting Concerns Identified

1. **Time dimension** — every computation step is timestamped; all modules must reason in `(position, timestamp)` pairs, not position alone
2. **Coordinate system** — consistent WGS84 lat/lon representation across all modules
3. **Configurable step size** — `--step` affects routing, tidal, and output simultaneously; must propagate without tight coupling
4. **Module interface contracts** — `routing` ↔ `tidal` and `routing` ↔ `cartography` must remain stable to allow data source replacement (NFR4/5)
5. **Safety threshold evaluation** — cross-cuts routing and condition management; the router must be able to query thresholds without owning them

## Starter Template Evaluation

### Primary Technology Domain

**Python CLI tool** — standalone application, no web framework, no database.

### Selected Stack: Typer + Poetry + pytest + ruff

**Rationale:**
- `Typer` uses native Python type hints for CLI flags — self-documenting, pedagogically clear, minimal boilerplate
- `Poetry` handles dependency management and packaging via `pyproject.toml` — current industry standard
- `ruff` replaces flake8/black in a single tool — enforces PEP 8 (NFR8) with no friction

**Initialization Commands:**

```bash
pip install poetry
poetry new voyageur
cd voyageur
poetry add typer
poetry add --group dev pytest ruff
```

**Initial Project Structure:**

```
voyageur/
├── pyproject.toml
├── voyageur/
│   ├── __init__.py
│   ├── main.py          # Typer CLI entry point
│   ├── routing/
│   ├── tidal/
│   ├── cartography/
│   └── cli/
└── tests/
    └── __init__.py
```

**Architectural Decisions Established:**

- **Language:** Python 3.11+
- **CLI framework:** Typer (flags declared as typed function parameters)
- **Packaging:** Poetry / pyproject.toml
- **Testing:** pytest (independent per module — NFR6)
- **Linting/Formatting:** ruff (PEP 8 compliance — NFR8)
- **Module structure:** four independent packages (`routing`, `tidal`, `cartography`, `cli`) from day one

**Note:** Project initialization using these commands is the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Module interface contracts (`TidalProvider`, `CartographyProvider` protocols) — must exist before routing module can be written
- Geospatial library selection — pyproj + shapely
- Routing algorithm approach for MVP — direct propagation

**Important Decisions (Shape Architecture):**
- Data storage format for tidal coefficients and cartographic data
- Makefile-based dev workflow

**Deferred Decisions (Post-MVP):**
- Full isochrone grid routing (required for multi-criteria and obstacle avoidance)
- External API integration patterns (SHOM, OpenMeteo)
- Web interface framework (Phase 3)
- CI/CD pipeline

### Data Architecture

**Tidal Coefficients:**
- Storage: YAML file embedded in package at `voyageur/tidal/data/ports.yaml`
- Contains: M2/S2 harmonic constants (amplitude, phase) for reference ports: Cherbourg, Le Havre, Saint-Malo
- Rationale: zero runtime dependency in MVP; Growth phase replaces with SHOM API client behind same interface

**Cartographic Data:**
- Storage: GeoJSON file embedded in package at `voyageur/cartography/data/normandy.geojson`
- Source: OpenSeaMap/OSM extract (Norman coast coastline and shallow-water polygons)
- Queried via shapely for obstacle intersection detection (FR6)
- Rationale: static file sufficient for MVP obstacle detection; Growth replaces with live OSM query behind same interface

**Boat Profile:**
- Storage: `~/.voyageur/boat.yaml` (user home directory, human-editable)
- Managed via `voyageur config` subcommand

### Geospatial Libraries

| Library | Role |
|---|---|
| `pyproj` | Geodesic calculations: distance, bearing, position advance on WGS84 ellipsoid |
| `shapely` | 2D geometry: route-to-coastline intersection for obstacle detection |

Both added via `poetry add pyproj shapely`.

### Module Interface Contracts

Each data-providing module exposes a `typing.Protocol` that the routing module depends on exclusively — never on concrete implementations:

```python
# voyageur/tidal/protocol.py
class TidalProvider(Protocol):
    def get_current(self, lat: float, lon: float, at: datetime) -> TidalState: ...

# voyageur/cartography/protocol.py
class CartographyProvider(Protocol):
    def intersects_land(self, route: list[Waypoint]) -> bool: ...
```

This enforces NFR4/5: swapping the concrete implementation (embedded data → live API) requires no changes to the routing module.

### Routing Algorithm

**MVP — Direct Propagation:**
At each time step:
1. Compute tidal current vector at current position and timestamp via `TidalProvider`
2. Compute wind-driven boat velocity from polar model + wind input
3. Sum vectors → effective velocity over ground
4. Advance position by `velocity × step_duration`
5. Evaluate safety thresholds; flag segment if breached
6. Check obstacle intersection via `CartographyProvider`; alert and halt if detected

**Growth — Full Isochrone Grid:**
Deferred to Phase 2. Required for multi-criteria routing and active obstacle avoidance (pathfinding).

### Infrastructure & Deployment

- Local install: `poetry install` → `voyageur` command available in PATH
- No cloud deployment, no CI/CD in MVP
- `Makefile` with targets: `install`, `test`, `lint`, `clean`

### Decision Impact Analysis

**Implementation Sequence:**
1. Project scaffold (Poetry, Typer, pytest, ruff, Makefile)
2. Module protocols (`TidalProvider`, `CartographyProvider`) + data models
3. `tidal` module: harmonic model from embedded YAML
4. `cartography` module: GeoJSON loader + shapely intersection
5. `routing` module: direct propagation algorithm
6. `cli` module: Typer commands (`voyageur`, `voyageur config`)
7. Integration + output formatting

**Cross-Component Dependencies:**
- `routing` depends on `TidalProvider` and `CartographyProvider` protocols (not implementations)
- `cli` depends on `routing` only
- `tidal` and `cartography` modules are fully independent of each other

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

6 areas where AI agents could make different choices without explicit rules.

### Naming Patterns

**Python Code Naming:**
- Functions and variables: `snake_case` → `get_tidal_current()`, `boat_speed`
- Classes: `PascalCase` → `TidalProvider`, `BoatProfile`
- Constants: `UPPER_SNAKE_CASE` → `DEFAULT_STEP_MINUTES = 15`
- Modules and files: `snake_case` → `tidal_model.py`, `route_planner.py`

**CLI Flag Naming (Typer):**
- All flags: `--kebab-case` → `--from`, `--to`, `--depart`, `--wind`, `--step`
- Wind format: `direction/speed` in degrees/knots → `240/15` (240° / 15 kn)
- Position format: `latN/lonW` → `49.65N/1.62W`
- Datetime format: ISO 8601 → `2026-03-29T08:00`

### Structure Patterns

**Test Organization:**
- All tests in `tests/` directory, mirroring `voyageur/` package structure
- Test file naming: `test_<module>.py` → `tests/test_tidal.py`, `tests/test_routing.py`
- Shared fixtures in `tests/conftest.py`
- No co-located tests alongside source code

**Module Internal Structure:**
- `voyageur/<module>/protocol.py` — `Protocol` interface definition
- `voyageur/<module>/impl.py` — concrete implementation
- `voyageur/models.py` — shared dataclasses (`BoatProfile`, `Waypoint`, `TidalState`, `WindCondition`, `Route`)

### Format Patterns

**CLI Output Format:**
- Maximum width: 80 columns (NFR3)
- Column separator: 2 spaces
- Section header: dashes `---`
- Timestamps: `HH:MM` format (not full ISO — too wide for 80 columns)
- Coordinates: `49.65N 1.62W` (6 significant figures)

**Internal Data Exchange:**
- All inter-module data uses Python `dataclass`, never plain `dict`
- No `print()` statements anywhere — all output via `typer.echo()`

### Process Patterns

**Error Handling:**
- User-facing errors (bad input, no route found): `typer.echo(message, err=True)` + `raise typer.Exit(1)`
- Internal errors (bugs): standard Python exceptions with descriptive messages
- Warnings (obstacle detected, threshold approached): `typer.echo(f"⚠ {message}", err=True)` — execution continues

**Alert Formatting:**
- Alert prefix: `⚠` for warnings, `✗` for blocking errors
- All alerts written to stderr (`err=True`), route timeline to stdout

### Enforcement Guidelines

**All AI Agents MUST:**
- Use `dataclass` for all data models — no bare dicts for domain objects
- Define `Protocol` in `protocol.py` before writing the concrete implementation
- Place all shared models in `voyageur/models.py` — no duplicate class definitions
- Route all output through `typer.echo()` — never `print()`
- Follow `--kebab-case` for all CLI flags without exception
- Write tests in `tests/` not co-located with source

**Anti-Patterns to Avoid:**
- ❌ `def get_TidalCurrent()` — mixed case in function name
- ❌ `routing.get_current({"lat": 49.0, "lon": 1.0})` — dict instead of dataclass
- ❌ `print(f"Position: {lat}, {lon}")` — direct print instead of typer.echo
- ❌ `--departureTime` — camelCase flag instead of `--depart`

## Project Structure & Boundaries

### Complete Project Directory Structure

```
voyageur/
├── Makefile                         # targets: install, test, lint, clean
├── pyproject.toml                   # Poetry: deps, build, ruff config
├── README.md
├── .gitignore
│
├── voyageur/                        # main package
│   ├── __init__.py
│   ├── models.py                    # shared dataclasses: BoatProfile, Waypoint,
│   │                                #   TidalState, WindCondition, Route
│   │
│   ├── cli/                         # FR1-FR6, FR10-FR16 — Typer entry points
│   │   ├── __init__.py
│   │   ├── main.py                  # voyageur command (plan)
│   │   └── config.py                # voyageur config subcommand
│   │
│   ├── routing/                     # FR1-FR6, FR17-FR19 — route computation
│   │   ├── __init__.py
│   │   ├── planner.py               # direct propagation algorithm
│   │   └── safety.py                # threshold evaluation (FR17-FR19)
│   │
│   ├── tidal/                       # FR7-FR9 — harmonic tidal model
│   │   ├── __init__.py
│   │   ├── protocol.py              # TidalProvider Protocol
│   │   ├── impl.py                  # HarmonicTidalModel (M2/S2)
│   │   └── data/
│   │       └── ports.yaml           # M2/S2 constants: Cherbourg, Le Havre, Saint-Malo
│   │
│   ├── cartography/                 # FR6 — coastline + obstacle detection
│   │   ├── __init__.py
│   │   ├── protocol.py              # CartographyProvider Protocol
│   │   ├── impl.py                  # GeoJSON-based implementation
│   │   └── data/
│   │       └── normandy.geojson     # Norman coast: coastline + shallow waters
│   │
│   └── output/                      # FR14-FR16 — CLI formatting
│       ├── __init__.py
│       └── formatter.py             # 80-col ASCII timeline + summary
│
└── tests/
    ├── conftest.py                  # shared fixtures (sample route, mock providers)
    ├── test_models.py               # dataclass validation
    ├── test_tidal.py                # TidalProvider + harmonic model (FR7-FR9)
    ├── test_cartography.py          # CartographyProvider + intersection (FR6)
    ├── test_routing.py              # propagation algorithm (FR1-FR5, FR17-FR19)
    ├── test_output.py               # formatter + 80-col constraint (NFR3)
    └── test_cli.py                  # CLI integration: flags, config (FR10-FR13)
```

### Architectural Boundaries

**Module Boundaries:**

| Module | Owns | Depends on |
|---|---|---|
| `cli` | User I/O, flag parsing, config file | `routing`, `output` |
| `routing` | Propagation algorithm, safety evaluation | `TidalProvider` protocol, `CartographyProvider` protocol |
| `tidal` | Harmonic model, port data | nothing |
| `cartography` | GeoJSON loading, intersection | nothing |
| `output` | 80-col formatting, table rendering | `models` |
| `models` | Shared dataclasses | nothing |

**Data Flow:**
```
CLI flags
  → BoatProfile (from ~/.voyageur/boat.yaml)
  → routing.planner (TidalProvider + CartographyProvider injected)
  → Route (list of Waypoints + TidalState + WindCondition per step)
  → output.formatter
  → stdout (timeline) / stderr (alerts)
```

### Requirements to Structure Mapping

| FR Group | Module | Files |
|---|---|---|
| FR1–FR5 (route input) | `cli`, `routing` | `cli/main.py`, `routing/planner.py` |
| FR6 (obstacle detection) | `cartography`, `routing` | `cartography/impl.py`, `routing/planner.py` |
| FR7–FR9 (tidal model) | `tidal` | `tidal/impl.py`, `tidal/data/ports.yaml` |
| FR10–FR13 (boat profile) | `cli` | `cli/config.py` |
| FR14–FR16 (output) | `output` | `output/formatter.py` |
| FR17–FR19 (safety thresholds) | `routing` | `routing/safety.py` |

### Development Workflow

```makefile
install:   poetry install
test:      poetry run pytest tests/ -v
lint:      poetry run ruff check voyageur/ tests/
format:    poetry run ruff format voyageur/ tests/
clean:     find . -type d -name __pycache__ -exec rm -rf {} +
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** Python 3.11+ / Typer / Poetry / pytest / ruff — no version conflicts. `pyproj` and `shapely` are mutually compatible and supported on Python 3.11+.

**Pattern Consistency:** `snake_case` / `PascalCase` / `Protocol` patterns are native to Python — no friction with the stack. `--kebab-case` is Typer's default behavior.

**Structure Alignment:** Module structure (`routing` / `tidal` / `cartography` / `output`) maps exactly to FR groups. Protocols in dedicated files, implementations in `impl.py` — consistent throughout.

### Requirements Coverage Validation ✅

**Functional Requirements:**

| FR Group | Coverage |
|---|---|
| FR1–FR6 Route Planning | ✅ `routing/planner.py` + `cli/main.py` |
| FR7–FR9 Tidal Model | ✅ `tidal/impl.py` + `tidal/data/ports.yaml` |
| FR10–FR13 Boat Profile | ✅ `cli/config.py` + `~/.voyageur/boat.yaml` |
| FR14–FR16 Output | ✅ `output/formatter.py` |
| FR17–FR19 Safety Thresholds | ✅ `routing/safety.py` |
| FR20–FR31 Growth Features | ⏸ Deferred — interfaces designed to accommodate them |

**Non-Functional Requirements:**

| NFR | Coverage |
|---|---|
| NFR1/2 Performance < 5s/30s | ✅ Direct propagation O(n) — n = number of steps |
| NFR3 80-column output | ✅ Explicit constraint in `output/formatter.py` |
| NFR4/5 Swappable interfaces | ✅ `Protocol` in `protocol.py` per module |
| NFR6 Independent tests | ✅ `tests/test_<module>.py` isolated per module |
| NFR7 Human-readable config | ✅ `~/.voyageur/boat.yaml` |
| NFR8 PEP 8 | ✅ Enforced by `ruff` |

### Gap Analysis Results

**No critical gaps detected.**

**Minor note:** `normandy.geojson` must be prepared before implementing the `cartography` module — this is a data preparation task (OSM extract), not an architectural gap.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context analyzed, complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped (time dimension, coordinate system, step size, protocols, safety thresholds)

**✅ Architectural Decisions**
- [x] Full stack specified: Python 3.11+, Typer, Poetry, pytest, ruff, pyproj, shapely
- [x] Module interface contracts defined (`TidalProvider`, `CartographyProvider`)
- [x] MVP routing algorithm specified (direct propagation)
- [x] Data storage formats decided (embedded YAML, GeoJSON)

**✅ Implementation Patterns**
- [x] Naming conventions established (6 conflict zones covered)
- [x] Module internal structure defined (`protocol.py` / `impl.py`)
- [x] CLI output format specified (80-col, HH:MM, stderr/stdout split)
- [x] Error handling patterns documented

**✅ Project Structure**
- [x] Complete directory structure defined (all files named)
- [x] FR groups mapped to specific modules and files
- [x] Component boundaries and dependency graph established
- [x] Implementation sequence ordered

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**
**Confidence Level: High**

**Key Strengths:**
- Protocol-based architecture: Growth phase requires zero rewrite of existing modules
- Centralized data models (`models.py`): no class duplication across modules
- Clear implementation sequence with explicit dependencies at each step

**First Implementation Step:**
```bash
poetry new voyageur && cd voyageur
poetry add typer pyproj shapely
poetry add --group dev pytest ruff
```

## GUI / Web Interface Architecture

_Section ajoutée 2026-04-15. Introduit une couche de présentation web-based en complément du CLI. Le noyau (routing, tidal, weather, boat profiles) reste inchangé — les protocoles existants (`TidalProvider`, `WeatherProvider`, etc.) sont réutilisés tels quels. Le formatter ASCII 80-col est conservé pour export._

### Intent & Scope

- **Objectif** : offrir une interface graphique interactive (carte, timeline, édition de profils, waypoints à la souris) en remplacement de l'usage terminal pour l'utilisateur final.
- **Positionnement** : nouvelle **couche de présentation**, pas un remplacement du noyau. Le CLI reste disponible (scripts, debug, export ASCII).
- **Déploiement v1** : local uniquement (single-user, pas d'auth).
- **Déploiement v2** : containerisable, multi-user à terme — l'architecture v1 doit rendre ce chemin possible sans refonte.

### Stack

| Couche | Choix | Justification |
|---|---|---|
| Backend HTTP | **FastAPI** + Uvicorn | Python, import direct des modules noyau, typage via Pydantic, WebSocket natif |
| Frontend | **Svelte + Vite** | Bundle léger, réactivité simple pour app mono-écran, TypeScript |
| Carte | **MapLibre GL JS** | WebGL pour rendu fluide des isochrones/traces, tuiles OpenSeaMap/OSM libres, pas de clé |
| Transport | **REST (CRUD) + WebSocket (streaming)** | REST pour profils/config, WebSocket pour progression calcul de route |
| Packaging | assets Svelte pré-buildés servis en statique par FastAPI | distribution `pip install` unique, pas de serveur web séparé |

### Structure du projet (ajout)

```
voyageur/
├── src/voyageur/              # noyau inchangé — protocoles préservés (NFR4)
│   ├── cli.py                 # conservé
│   ├── formatter_ascii.py     # conservé pour export
│   ├── tidal/
│   ├── weather/
│   ├── routing/
│   └── models.py
├── src/voyageur_web/          # NOUVEAU — couche présentation
│   ├── __init__.py
│   ├── app.py                 # FastAPI instance, montage des routes + assets
│   ├── main.py                # CLI entry point `voyageur-web` (lance uvicorn + ouvre navigateur)
│   ├── routes/
│   │   ├── routes.py          # POST /api/routes (calcul), GET /api/routes/{id}
│   │   ├── profiles.py        # CRUD /api/boat-profiles
│   │   ├── config.py          # GET/PUT /api/config
│   │   └── ws.py              # WS /ws/route/{id} — streaming isochrones + timeline
│   ├── schemas.py             # Pydantic — mapping models.py ↔ JSON API
│   └── static/                # assets Svelte buildés (web/dist)
└── web/                       # NOUVEAU — sources frontend
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── App.svelte
    │   ├── lib/
    │   │   ├── api.ts              # client REST typé
    │   │   ├── ws.ts               # client WebSocket
    │   │   └── types.ts            # miroir des schémas Pydantic
    │   ├── components/
    │   │   ├── Map.svelte          # MapLibre : trace, isochrones, waypoints
    │   │   ├── Timeline.svelte     # timeline tidale/météo
    │   │   ├── BoatProfileForm.svelte
    │   │   └── RouteForm.svelte    # départ/arrivée/heure
    │   └── stores/                 # état Svelte (route courante, profil actif)
    └── dist/                       # généré par `npm run build`, copié vers src/voyageur_web/static/
```

### Contrats couche par couche

- **Noyau → API** : `voyageur_web/routes/*.py` importe directement `voyageur.routing`, `voyageur.tidal`, `voyageur.weather`. Aucune duplication de logique. Les protocoles existants sont injectés via un container d'app simple (fonction factory dans `app.py`).
- **API → Front** : schémas Pydantic dans `schemas.py` = source de vérité. `web/src/lib/types.ts` est généré (ou maintenu à la main) pour refléter ces schémas.
- **Front → Carte** : `Map.svelte` ne connaît que des GeoJSON — toute conversion route/isochrone → GeoJSON se fait côté API ou dans `lib/api.ts`.

### Communication temps réel

Le calcul de route peut être long (isochrones multi-critères, appels SHOM/OpenMeteo). Le flux :

1. `POST /api/routes` → accepte la requête, renvoie `{route_id, ws_url}` immédiatement
2. Le backend lance le calcul dans une task asyncio
3. Le front ouvre `WS /ws/route/{route_id}` et reçoit des messages typés :
   - `{type: "isochrone", step, geojson}` — à chaque propagation
   - `{type: "waypoint_added", ...}`
   - `{type: "complete", route_summary}` ou `{type: "error", ...}`
4. La carte et la timeline se mettent à jour de façon incrémentale.

### Chemin de déploiement

| Étape | État | Implication |
|---|---|---|
| v1 — local | `voyageur-web` lance uvicorn sur `127.0.0.1:8765`, ouvre le navigateur par défaut | pas d'auth, config locale `~/.voyageur/config.yaml` |
| v2 — containerisé | Dockerfile multi-stage (build Svelte + runtime Python), variables d'env pour secrets | ajouter auth (token ou OAuth proxy), CORS configuré, logs structurés |
| v2 — multi-user | sessionisation, isolation des profils par user | introduire un store (SQLite → Postgres), refactor `boat_profile_manager` avec scope user |

L'architecture v1 rend v2 possible en gardant **toute la logique métier pure dans le noyau** (pas d'état global, protocoles injectés) et en isolant la persistance utilisateur dans `voyageur_web/`.

### Dépendances ajoutées

```toml
# pyproject.toml — group "web"
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.32"}
websockets = "^13"
pydantic = "^2"
```

```json
// web/package.json — extraits
"svelte": "^5",
"vite": "^5",
"maplibre-gl": "^4",
"typescript": "^5"
```

### Impact sur les décisions existantes

- **Protocoles (NFR4)** : inchangés. La GUI est un consommateur de plus, au même titre que le CLI.
- **Formatter ASCII 80-col** : conservé, exposé via `GET /api/routes/{id}/export?format=ascii` pour export téléchargeable.
- **Boat profiles** : le manager existant reste seule source de vérité ; l'API le wrap.
- **Tests** : ajouter `tests/test_web/` avec `TestClient` FastAPI (mocks HTTP pour SHOM/OpenMeteo déjà en place).

### Nouveaux épics suggérés

- **Épic 6 — Web GUI Foundation** : FastAPI app, routes CRUD profils/config, Svelte scaffold, build pipeline.
- **Épic 7 — Interactive Map & Route Planning** : MapLibre, saisie waypoints, calcul de route via WS, affichage isochrones.
- **Épic 8 — Timeline & Boat Profile UI** : timeline tidale/météo, formulaire profils, intégration live data.
- **Épic 9 — Deployable Packaging** : Dockerfile, auth, config multi-user (v2).
