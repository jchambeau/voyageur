---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments: ['_bmad-output/planning-artifacts/prd.md', '_bmad-output/planning-artifacts/architecture.md']
---

# Voyageur - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Voyageur, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can compute a direct route between two named Norman coast ports
FR2: User can compute a route between two geographic coordinates
FR3: User can specify departure time for route computation
FR4: User can specify wind conditions (direction and speed) as route input
FR5: User can specify the time step interval for route computation (1, 5, 15, 30, 60 min; default 15)
FR6: System alerts user when the direct route intersects land or shallow areas
FR7: System computes tidal current (direction and speed) at any Norman coast point for a given timestamp
FR8: System integrates tidal current into route calculation at each time step
FR9: System displays tidal current at each step in the route timeline
FR10: User can create and save a persistent boat profile
FR11: User can update a saved boat profile
FR12: System loads saved boat profile automatically at runtime
FR13: User can override boat profile parameters for a single route computation
FR14: System displays a per-step route timeline (position, heading, SOG, wind, tidal current)
FR15: System displays a passage summary: total distance, estimated duration, key decision points
FR16: System alerts user when no viable route exists within safety parameters
FR17: User can define safety threshold parameters (max wind speed, max tidal current, max distance from nearest shelter)
FR18: System evaluates each route segment against user-defined safety thresholds
FR19: System flags segments where conditions approach or exceed safety thresholds
FR20: [Growth] User can request route re-computation from a current position and time with updated conditions
FR21: [Growth] System proposes alternative routes when the original route becomes unviable
FR22: [Growth] System notifies user when the active route is no longer safe
FR23: [Growth] System computes and presents multiple simultaneous route options per passage
FR24: [Growth] User can request a route optimized for fastest passage time
FR25: [Growth] User can request a route optimized for sailing comfort
FR26: [Growth] User can request a route maximizing proximity to shelter
FR27: [Growth] User can request a route minimizing maritime traffic exposure
FR28: [Growth] System suggests an optimal departure time window for a given passage
FR29: [Growth] System retrieves real tidal data from an external source (SHOM API)
FR30: [Growth] System retrieves wind and weather forecast data from an external source
FR31: [Growth] System uses retrieved forecast data as route input in place of manual wind parameters

### NonFunctional Requirements

NFR1: Route computation for a Norman coast passage (< 100 NM) completes in under 5 seconds at the default 15-minute step
NFR2: Route computation at 1-minute step on the same passage completes in under 30 seconds
NFR3: Full timeline output fits a standard 80-column terminal without truncation for typical passages
NFR4: Tidal model module exposes a documented interface (TidalProvider Protocol) enabling replacement with SHOM API client without changes to routing module
NFR5: Cartographic data layer exposes a documented interface (CartographyProvider Protocol) enabling replacement with live OpenSeaMap data without changes to routing or CLI modules
NFR6: Each core module (routing, tidal, cartography, cli) has independent unit tests executable in isolation
NFR7: Boat profile stored in human-readable YAML, editable without a dedicated tool
NFR8: Codebase follows PEP 8 conventions throughout (enforced by ruff)

### Additional Requirements

- Project scaffold: Python 3.11+ with Poetry (pyproject.toml), Typer (CLI framework), pytest (testing), ruff (linting/formatting), pyproj + shapely (geospatial), Makefile with targets: install, test, lint, format, clean
- Module protocols defined first: TidalProvider and CartographyProvider as typing.Protocol in dedicated protocol.py files — must exist before routing module is written
- Shared data models: All domain objects as Python dataclasses in voyageur/models.py (BoatProfile, Route, Waypoint, TidalState, WindCondition) — no duplicate definitions across modules
- Tidal data: Embedded YAML at voyageur/tidal/data/ports.yaml with M2/S2 harmonic constants (amplitude, phase) for reference ports: Cherbourg, Le Havre, Saint-Malo
- Cartographic data: Embedded GeoJSON at voyageur/cartography/data/normandy.geojson — Norman coast coastline and shallow-water polygons sourced from OpenSeaMap/OSM
- Boat profile storage: ~/.voyageur/boat.yaml (human-editable, managed via `voyageur config` subcommand)
- CLI output routing: All output via typer.echo() — never print(); route timeline to stdout, alerts and errors to stderr
- Error handling patterns: User-facing errors → typer.echo(err=True) + raise typer.Exit(1); warnings (⚠) → continue execution; blocking errors (✗) → halt
- Module internal structure: each data-providing module has protocol.py (Protocol definition) + impl.py (concrete implementation)
- Test organization: all tests in tests/ directory mirroring package structure — no co-located tests; shared fixtures in tests/conftest.py
- CLI flag naming: --kebab-case for all flags (--from, --to, --depart, --wind, --step, --boat); wind format: direction/speed (e.g., 240/15); datetime: ISO 8601 (e.g., 2026-03-29T08:00)
- Implementation sequence: scaffold → models + protocols → tidal module → cartography module → routing module → cli module → output module → integration

### UX Design Requirements

N/A — CLI application, no UX design document.

### FR Coverage Map

FR1:  Epic 2 — route depuis port nommé
FR2:  Epic 2 — route depuis coordonnées géographiques
FR3:  Epic 2 — heure de départ
FR4:  Epic 2 — paramètres vent (direction/vitesse)
FR5:  Epic 2 — pas de temps configurable
FR6:  Epic 3 — alerte intersection terre/hauts-fonds
FR7:  Epic 2 — calcul courant tidal (position + timestamp)
FR8:  Epic 2 — intégration tidal dans le routing
FR9:  Epic 2 — affichage tidal dans la timeline
FR10: Epic 3 — création profil bateau persistant
FR11: Epic 3 — mise à jour profil bateau
FR12: Epic 2 — chargement automatique du profil bateau
FR13: Epic 3 — override profil bateau pour une route
FR14: Epic 2 — timeline par étape (position, cap, SOG, vent, tidal)
FR15: Epic 2 — résumé de traversée (distance, durée, points clés)
FR16: Epic 3 — alerte aucune route viable
FR17: Epic 3 — définition des seuils de sécurité
FR18: Epic 3 — évaluation des segments vs seuils
FR19: Epic 3 — flags segments critiques
FR20: Epic 4 — re-planification depuis position courante
FR21: Epic 4 — proposition d'alternatives si route non viable
FR22: Epic 4 — notification route active non sûre
FR23: Epic 4 — calcul de routes multiples simultanées
FR24: Epic 4 — route la plus rapide
FR25: Epic 4 — route la plus confortable
FR26: Epic 4 — route maximisant proximité abris
FR27: Epic 4 — route minimisant trafic maritime
FR28: Epic 4 — suggestion heure de départ optimale
FR29: Epic 5 — données tidal réelles (SHOM API)
FR30: Epic 5 — prévisions météo/vent (API externe)
FR31: Epic 5 — données récupérées comme input routing

## Epic List

### Epic 1: Fondation du projet & contrats de modules
Le projet est installable, testable, et extensible. Tous les dataclasses partagés et interfaces de modules sont en place. Chaque module peut être développé indépendamment sans bloquer les autres.
**FRs covered:** Architecture requirements only
**NFRs covered:** NFR6, NFR8

### Epic 2: Planification de passage avec marée
JC peut planifier un passage côtier Normand et voir, étape par étape, sa position, sa vitesse et les conditions de courant de marée évoluant tout au long de la route.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR7, FR8, FR9, FR12, FR14, FR15
**NFRs covered:** NFR1, NFR2, NFR3, NFR4, NFR5

### Epic 3: Navigation sécurisée & profil bateau
JC peut enregistrer son profil bateau et recevoir des alertes quand la route intersecte un obstacle ou dépasse ses seuils de sécurité.
**FRs covered:** FR6, FR10, FR11, FR13, FR16, FR17, FR18, FR19
**NFRs covered:** NFR7

### Epic 4: [Growth] Routage intelligent multi-critères
JC peut comparer plusieurs routes optimisées selon différents critères, recevoir une suggestion d'heure de départ optimale, et re-planifier en cours de route si les conditions changent.
**FRs covered:** FR20, FR21, FR22, FR23, FR24, FR25, FR26, FR27, FR28

### Epic 5: [Growth] Intégration de données temps réel
Le système récupère automatiquement les données de marée et météo réelles, remplaçant les paramètres saisis manuellement.
**FRs covered:** FR29, FR30, FR31

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Project Foundation & Module Contracts

Set up the project scaffold and define all shared data contracts so that every module can be developed and tested independently from day one.

### Story 1.1: Project Scaffold Setup

As a developer,
I want to initialize the Voyageur project with Poetry, Typer, pytest, ruff, and a Makefile,
So that the project can be installed, run, and tested from day one with consistent tooling.

**Acceptance Criteria:**

**Given** a fresh development environment with Python 3.11+ and Poetry installed
**When** I run `poetry install`
**Then** all dependencies are installed: typer, pyproj, shapely, pytest, ruff
**And** `voyageur --help` outputs a usage message with exit code 0
**And** `make test` runs the (empty) test suite and exits with code 0
**And** `make lint` runs ruff on `voyageur/` and `tests/` with no errors
**And** the project structure matches the architecture spec: `voyageur/` package with `__init__.py`, `tests/` directory

### Story 1.2: Shared Data Models

As a developer,
I want all domain data models defined as typed dataclasses in `voyageur/models.py`,
So that every module shares the same data contracts without duplication.

**Acceptance Criteria:**

**Given** the voyageur package is installed
**When** I import from `voyageur.models`
**Then** `BoatProfile`, `Waypoint`, `TidalState`, `WindCondition`, and `Route` are importable as dataclasses
**And** each field is typed (no bare `Any`): `BoatProfile` has name, loa, draft, sail_area, default_step; `Waypoint` has lat, lon, timestamp, heading, speed_over_ground; `TidalState` has timestamp, current_direction, current_speed, water_height; `WindCondition` has timestamp, direction, speed; `Route` has waypoints list, departure_time, total_duration
**And** `tests/test_models.py` passes: each dataclass instantiated with valid data, fields accessible
**And** `make lint` reports no violations on `models.py`

### Story 1.3: Module Interface Protocols

As a developer,
I want `TidalProvider` and `CartographyProvider` defined as `typing.Protocol`,
So that the routing module can be written and tested with mock implementations, independently of the concrete tidal and cartography modules.

**Acceptance Criteria:**

**Given** the voyageur package is installed
**When** I import `TidalProvider` from `voyageur.tidal.protocol`
**Then** it defines `get_current(self, lat: float, lon: float, at: datetime) -> TidalState`
**When** I import `CartographyProvider` from `voyageur.cartography.protocol`
**Then** it defines `intersects_land(self, route: list[Waypoint]) -> bool`
**And** a minimal mock class implementing each protocol satisfies `isinstance(mock, TidalProvider)` via `Protocol` structural check
**And** `tests/test_models.py` (or a dedicated `tests/test_protocols.py`) verifies mock compliance
**And** `make lint` reports no violations on `tidal/protocol.py` and `cartography/protocol.py`

## Epic 2: Tidal-Aware Passage Planning

JC can plan a Norman coast passage and see, step by step, his position, speed, and tidal current conditions evolving throughout the route.

### Story 2.1: Harmonic Tidal Model

As JC,
I want the system to compute tidal current direction and speed at any Norman coast point and timestamp using harmonic constituents,
So that tidal conditions can be accurately integrated into my route calculations.

**Acceptance Criteria:**

**Given** `voyageur/tidal/data/ports.yaml` contains M2 and S2 harmonic constants (amplitude, phase) for Cherbourg, Le Havre, and Saint-Malo
**When** I call `HarmonicTidalModel.get_current(lat, lon, at)` for a point near a reference port
**Then** it returns a `TidalState` with non-zero current_direction and current_speed
**And** the model interpolates between reference ports for intermediate positions
**And** `HarmonicTidalModel` satisfies the `TidalProvider` protocol
**And** `tests/test_tidal.py` passes: at least 3 reference ports tested, current reverses direction over a 6-hour window (expected tidal cycle), values within realistic Norman coast range (0–5 kn)
**And** `make lint` reports no violations on `tidal/`

### Story 2.2: Direct Route Propagation Algorithm

As JC,
I want the system to compute a time-stepped route by combining wind and tidal current at each step,
So that I can see my estimated position at every interval throughout my passage.

**Acceptance Criteria:**

**Given** an origin, destination, departure_time, wind (direction + speed), step_minutes, and injected TidalProvider and CartographyProvider
**When** I call `RoutePlanner.compute()`
**Then** it returns a `Route` with one `Waypoint` per time step from origin to destination
**And** each `Waypoint` has lat, lon, timestamp, heading, and speed_over_ground computed from wind vector + tidal current vector
**And** boat speed is derived from the `BoatProfile` polar model (simplified: constant VMG fraction based on wind angle)
**And** the route terminates when destination is reached (within tolerance) or max_steps is exceeded
**And** `tests/test_routing.py` passes a Cherbourg→Granville scenario with mock TidalProvider and mock CartographyProvider
**And** computation of a 100 NM passage at 15 min step completes in under 5 s (NFR1)

### Story 2.3: ASCII 80-Column Output Formatter

As JC,
I want the route computation results displayed as a structured ASCII table that fits an 80-column terminal,
So that I can read my passage plan clearly without wrapping or truncation.

**Acceptance Criteria:**

**Given** a computed `Route` object
**When** I call `format_timeline(route)`
**Then** it returns a string with a header row and one data row per waypoint
**And** each row contains: elapsed time (HH:MM), position (lat/lon), heading (°), SOG (kn), tidal current (dir/spd), wind (dir/spd)
**And** every row is ≤ 80 characters wide
**And** a summary section follows the table: total distance (NM), estimated duration, count of decision-point flags
**And** `tests/test_output.py` passes: 80-col constraint verified on a sample route of at least 20 steps
**And** `make lint` reports no violations on `output/`

### Story 2.4: CLI Route Planning Command

As JC,
I want to run `voyageur --from Cherbourg --to Granville --depart 2026-03-29T08:00 --wind 240/15` and see the full route timeline,
So that I can plan a coastal passage from my terminal in seconds.

**Acceptance Criteria:**

**Given** the voyageur command is installed
**When** I run `voyageur --from PORT --to PORT --depart ISO8601 --wind DIR/SPD`
**Then** the route timeline is printed to stdout and the command exits with code 0
**And** port names resolve to coordinates for at least: Cherbourg, Granville, Le Havre, Saint-Malo, Barfleur, Saint-Vaast-la-Hougue, Honfleur
**And** `--from` and `--to` also accept `latN/lonW` coordinates (FR2)
**And** `--step` flag sets the time step in minutes (1, 5, 15, 30, 60); default is 15 (FR5)
**And** if `~/.voyageur/boat.yaml` exists it is loaded automatically; if absent a default profile is used with a notice on stderr (FR12)
**And** user-facing errors (unknown port, invalid wind format) print to stderr and exit with code 1
**And** `tests/test_cli.py` passes a happy-path Cherbourg→Granville invocation and an invalid-port error case

## Epic 3: Safe Navigation & Boat Profile

JC can save his boat profile and receive alerts when the route intersects an obstacle or exceeds his safety thresholds.

### Story 3.1: Coastal Obstacle Detection

As JC,
I want the system to detect when my planned route crosses land or shallow waters on the Norman coast,
So that I receive an alert before departing on a route that passes through an obstacle.

**Acceptance Criteria:**

**Given** `voyageur/cartography/data/normandy.geojson` contains Norman coast coastline and shallow-water polygons from OpenSeaMap/OSM
**When** `GeoJsonCartography.intersects_land(route)` is called with a route that crosses land or a shallow area
**Then** it returns `True` and the CLI prints a `⚠` alert to stderr identifying the approximate position of the intersection
**When** called with a clear offshore route
**Then** it returns `False` and no alert is printed
**And** `GeoJsonCartography` satisfies the `CartographyProvider` protocol
**And** route computation continues after the alert (obstacle detection does not halt execution)
**And** `tests/test_cartography.py` passes: at least one intersecting route and one clear route tested
**And** `make lint` reports no violations on `cartography/`

### Story 3.2: Safety Threshold Evaluation

As JC,
I want to define maximum acceptable wind speed, tidal current speed, and distance from nearest shelter, and have each route segment evaluated against these thresholds,
So that dangerous segments are flagged before I depart.

**Acceptance Criteria:**

**Given** safety thresholds set via CLI flags `--max-wind` (kn), `--max-current` (kn), `--max-dist-shelter` (NM) or loaded from `boat.yaml`
**When** a route segment's wind speed exceeds `--max-wind` or tidal current speed exceeds `--max-current`
**Then** that waypoint is flagged with a `⚠` marker in the timeline output
**And** the passage summary shows the count and timestamps of all flagged segments
**When** all segments are flagged (no viable conditions throughout the route)
**Then** a `✗` error is printed to stderr and the command exits with code 1 (FR16)
**And** `tests/test_routing.py` passes safety evaluation tests: a route with one flagged segment and a route where all segments are flagged
**And** `make lint` reports no violations on `routing/safety.py`

### Story 3.3: Boat Profile Management

As JC,
I want to create and update a persistent boat profile with `voyageur config`,
So that my boat's characteristics are saved once and loaded automatically for every passage plan.

**Acceptance Criteria:**

**Given** the voyageur command is installed
**When** I run `voyageur config --name "Mon Bateau" --loa 12.5 --draft 1.8 --sail-area 65 --default-step 15`
**Then** the profile is saved to `~/.voyageur/boat.yaml` (directory created if absent)
**And** the file is human-readable YAML with all fields present (NFR7)
**When** I run `voyageur config --show`
**Then** the current saved profile is displayed to stdout
**When** I run `voyageur --from X --to Y --depart T --wind W --draft 2.1`
**Then** the route is computed using draft 2.1 instead of the saved value, all other fields from the saved profile (FR13)
**And** `tests/test_cli.py` passes: config create, config show, and per-run override tests
**And** `make lint` reports no violations on `cli/config.py`

## Epic 4: [Growth] Intelligent Multi-Criteria Routing

JC can compare multiple optimised routes, receive an optimal departure time suggestion, and re-plan mid-passage when conditions change.

### Story 4.1: Isochrone Grid with Obstacle Avoidance

As JC,
I want the system to compute routes that automatically avoid land and shallow waters,
So that I receive viable routes even when the direct line crosses an obstacle.

**Acceptance Criteria:**

**Given** a departure point, destination, and a CartographyProvider with Norman coast data
**When** the direct route would cross an obstacle
**Then** the isochrone grid algorithm finds and returns the shortest viable route around it
**And** the returned route is a sequence of waypoints with no segment intersecting land or shallow areas
**And** computation of a Norman coast passage with obstacle avoidance completes in under 30 s at 1-min step (NFR2)
**And** `tests/test_routing.py` passes: a route requiring obstacle avoidance returns a valid detour; a direct clear route is unchanged

### Story 4.2: Multi-Criteria Route Computation

As JC,
I want the system to compute and display multiple route options simultaneously — fastest, most comfortable, nearest shelter, least traffic —
So that I can choose the route that best fits conditions and my preferences for each passage.

**Acceptance Criteria:**

**Given** a passage request with `--criteria all` (or individual flags: `--fastest`, `--comfort`, `--shelter`, `--traffic`)
**When** the route planning command runs
**Then** up to four routes are computed and displayed side by side or sequentially with distinct labels
**And** the fastest route minimizes total passage time
**And** the comfort route minimizes exposure to high wind angles and swell
**And** the shelter route maximizes proximity to harbours throughout the passage
**And** the traffic route minimizes crossing of known shipping lanes
**And** `tests/test_routing.py` passes: multi-criteria output for a Cherbourg→Granville scenario returns at least two distinct routes

### Story 4.3: Optimal Departure Time Suggestion

As JC,
I want the system to suggest the optimal departure time window for a given passage,
So that tidal currents work in my favour and I can save significant time without manually iterating departure times.

**Acceptance Criteria:**

**Given** a passage request with `--optimize-departure` flag and a search window (e.g. `--window 2026-03-29T06:00/2026-03-29T12:00`)
**When** the command runs
**Then** the system evaluates departure times across the window at configurable intervals
**And** it returns the departure time that minimizes total passage duration (or maximises favourable tidal current)
**And** the output explains the recommendation: e.g. "Optimal departure: 06:30 — tidal current at Raz Blanchard turns favourable, saving 45 min vs 08:00"
**And** `tests/test_routing.py` passes: optimal departure test over a 6-hour window returns a departure time earlier than the naive option

### Story 4.4: Route Re-planning from Current Position

As JC,
I want to re-plan my route from my current position with updated conditions,
So that if wind or sea state changes mid-passage I can immediately get new viable options.

**Acceptance Criteria:**

**Given** an existing passage plan and updated conditions (current position, time, new wind)
**When** I run `voyageur replan --from CURRENT_POS --time NOW --wind NEW_WIND --to DESTINATION`
**Then** the system computes a new route from the current position to the original destination
**And** if the new route is viable, it is displayed as a timeline (same format as Epic 2)
**And** if no viable route exists within safety parameters, a `✗` alert is printed with the next viable departure window (FR22)
**And** if multiple criteria are available (from Story 4.2), alternative routes are proposed (FR21)
**And** `tests/test_cli.py` passes: a replan invocation with changed wind produces a new route distinct from the original

## Epic 5: [Growth] Live Data Integration

The system automatically retrieves real tidal and weather data, replacing manually entered parameters.

### Story 5.1: SHOM Tidal API Client

As JC,
I want the system to retrieve real tidal data from the SHOM API instead of the embedded harmonic model,
So that my route calculations use authoritative French hydrographic data without any manual input.

**Acceptance Criteria:**

**Given** a valid SHOM API key configured in `~/.voyageur/config.yaml`
**When** `ShomTidalClient.get_current(lat, lon, at)` is called
**Then** it queries the SHOM API and returns a `TidalState` for the requested position and timestamp
**And** `ShomTidalClient` satisfies the `TidalProvider` protocol — the routing module requires no changes (NFR4)
**And** if the API is unavailable, the system falls back to the embedded harmonic model with a `⚠` notice on stderr
**And** `tests/test_tidal.py` passes: SHOM client tested with mocked HTTP responses; fallback behaviour tested
**And** `make lint` reports no violations on `tidal/shom_client.py`

### Story 5.2: Weather Forecast API Client

As JC,
I want the system to retrieve wind and weather forecast data from an external API,
So that I no longer need to enter wind conditions manually and my route reflects real forecast data.

**Acceptance Criteria:**

**Given** an external weather API configured (OpenMeteo or Météo-France, no API key required for OpenMeteo)
**When** I run `voyageur --from X --to Y --depart T` without `--wind`
**Then** the system fetches the wind forecast for the departure area and time window and uses it as route input (FR31)
**And** the timeline output indicates that forecast data is in use (e.g. "Wind: forecast (OpenMeteo)" in summary)
**And** wind conditions are re-fetched per time step for the forecast period, reflecting forecast evolution along the route
**And** if the API is unavailable and no `--wind` flag is provided, the command exits with a `✗` error asking the user to provide `--wind` manually
**And** `tests/test_cli.py` passes: weather integration tested with mocked HTTP responses; fallback error tested
**And** `make lint` reports no violations on relevant modules
