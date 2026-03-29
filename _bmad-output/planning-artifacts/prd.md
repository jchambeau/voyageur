---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedAt: '2026-03-28'
inputDocuments: []
workflowType: 'prd'
briefCount: 0
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
classification:
  projectType: 'Python CLI (evolving to web)'
  domain: 'Maritime Navigation / Geospatial'
  complexity: 'medium'
  projectContext: 'greenfield'
  geographicScope: 'Norman coast (France)'
  initialDataModel: 'constant wind, no external APIs'
  targetUser: 'JC (solo, personal learning project)'
---

# Product Requirements Document — Voyageur

**Author:** JC
**Date:** 2026-03-28

## Executive Summary

Voyageur is a multi-criteria sailing route planning tool for coastal navigation on the Norman coast of France. It targets solo skippers solving the core problem of dynamic passage decision-making under changing environmental conditions — wind, tides, weather — that static paper charts cannot address. The product serves a dual purpose: practical navigation planning and progressive skill-building in cartography, geospatial programming, and maritime routing algorithms.

**What makes it special:** Voyageur treats coastal sailing as a constrained optimization problem with dynamic parameters. It simultaneously proposes multiple routes optimized against distinct criteria (fastest, most comfortable, nearest shelter, least traffic) and projects tidal currents and weather evolution across the full journey timeline — so the skipper anticipates, not reacts. On the Norman coast, where tidal range reaches 14m, this time-aware approach is safety-critical, not merely convenient.

## Project Classification

- **Project Type:** Python CLI application, evolving toward a web interface
- **Domain:** Maritime navigation / Geospatial
- **Complexity:** Medium — progressive architecture, starts simple, adds layers incrementally
- **Project Context:** Greenfield, personal learning project
- **Geographic Scope:** Norman coast, France (initial)
- **Data Model:** Constant wind and simulated tidal data initially; external APIs in future iterations

## Success Criteria

### User Success

- User plans a Norman coast passage and views the full route with conditions (wind, tidal current) evolving over time
- User departs with confidence: route display provides sufficient certainty that no navigational surprises will occur
- Route calculation completes within interactive planning session time (< 5 seconds for typical passages)

### Learning & Project Success

- Tool is genuinely used for real passage planning on the Norman coast
- Each development iteration ships a working, demonstrable capability
- Cartography subsystem is hand-built (not black-boxed), directly exercising the learning objective

### Technical Success

- Correct geospatial route computation between two coastal waypoints
- Tidal current simulation integrated as a first-class parameter in route calculation and display
- Modular architecture enabling progressive addition of route criteria and data sources without structural rework

### Measurable Outcomes

- MVP: two ports in → fastest route out, with per-step tidal/wind conditions displayed on a configurable timeline
- Each major iteration ships one new route criterion or one new data source integration
- All four core modules (`routing`, `tidal`, `cartography`, `cli`) independently testable from day one

## Product Scope & Roadmap

### Phase 1 — MVP

**Core journey supported:** Journey 1 — Planned Passage

- Single `voyageur` command with flags: `--from`, `--to`, `--depart`, `--wind`, `--step`
- `voyageur config` subcommand to create/update persistent boat profile
- Direct route computation (great-circle line) between two Norman coast ports
- Obstacle detection: alert if route intersects land or shallow areas — no automatic rerouting
- Simplified harmonic tidal model (M2/S2 constituents) for key Norman reference ports
- Configurable time step (default 15 min; supports 1, 5, 15, 30, 60 min)
- ASCII timeline output: position, heading, speed, tidal current, wind per step
- Constant wind model (direction + speed as manual input)

**Explicitly out of MVP:** obstacle avoidance/rerouting, multiple route criteria, passage plan export, any external API integration.

### Phase 2 — Growth

- Pathfinding with obstacle avoidance (grid-based routing on maritime space)
- Multiple simultaneous routes: fastest, most comfortable, closest to shelter, least traffic
- Optimal departure time suggestion (automatically compute best departure window)
- Real tidal data integration (SHOM API)
- Real weather/wind forecast integration (OpenMeteo or Météo-France)
- Re-planning from current position with condition change alerts

### Phase 3 — Vision

- Web interface with interactive map and route visualization
- Real-time condition monitoring with alerts (wind shift, approaching storm)
- GPX/JSON route export
- Extended geographic coverage beyond the Norman coast

## User Journeys

### Journey 1 — The Planned Passage (MVP — Happy Path)

**Persona:** JC wants to sail Cherbourg → Granville on Saturday morning. Today: 45 minutes at the chart table, tide almanac open, weather on his phone, ruler on the paper chart. He knows approximately where he'll be at noon — "approximately" is the word that chafes.

**Opening scene:** Eve of departure, 8pm. JC opens his terminal.

```
$ voyageur --from Cherbourg --to Granville \
    --depart 2026-03-29T08:00 \
    --wind 240/15
```

**Climax (MVP):** The timeline shows that at 11:30, passing Raz Blanchard, the tidal current runs against him at 2.5 knots. He re-runs with `--depart 2026-03-29T06:30` — the current becomes favorable. 10 seconds vs. an hour with the almanac.

**Climax (Growth):** Voyageur suggests directly: *"Optimal departure: 06:30 — tidal current at Raz Blanchard turns favorable, saving 45 min vs 08:00 departure."*

**Resolution:** JC departs with an optimized plan and the certainty that tides are working in his favor.

---

### Journey 2 — Changing Conditions (Growth — Edge Case)

**Note:** This journey requires re-planning from position and passage plan persistence, both Growth features.

**Opening scene:** JC planned Honfleur → Barfleur. Mid-passage, wind veers 30° and strengthens. Conditions diverge from plan.

```
$ voyageur replan --plan honfleur-barfleur.json \
    --current-position 49.52N/1.18W \
    --time 2026-03-29T11:15 \
    --wind 270/22
```

**Climax:** Alert: *"Route no longer viable — beam reach 22kn swell at WP3. Two alternatives proposed."* Option A: extended north in the lee of the coast. Option B: stopover at Saint-Vaast-la-Hougue.

**Resolution:** JC chooses the stopover. An unexpected situation becomes an informed decision, not a stressful one.

---

### Journey 3 — No Safe Route (Growth — Abort Scenario)

**Opening scene:** Weather deteriorating faster than forecast. All routes exceed safety thresholds.

**Climax:** *"No viable route within safety parameters. Recommend staying at current port. Next viable window: tomorrow 07:00."*

**Resolution:** JC stays in port with a clear next window — no frustration, no guesswork.

---

### Journey Requirements Summary

| Capability | Phase | Journey |
|---|---|---|
| Port/coordinate input + boat profile | MVP | J1 |
| Manual wind parameters + departure time | MVP | J1 |
| Tidal current simulation on timeline | MVP | J1 |
| Configurable time step | MVP | J1 |
| ASCII timeline output | MVP | J1 |
| Obstacle detection alert | MVP | J1 |
| Safety threshold evaluation | MVP | J1, J3 |
| Passage plan export/reload | Growth | J2 |
| Re-planning from current position | Growth | J2 |
| Alert when route unviable + alternatives | Growth | J2, J3 |
| Optimal departure time suggestion | Growth | J1 |
| Next viable window notification | Growth | J3 |

## Domain Requirements

### Cartographic Data

- Source: OpenSeaMap (OpenStreetMap-based) for coastline, ports, and hazard overlays; SHOM open data for French coastal charts where available
- No commercial licensing required — personal/educational use
- Cartography layer isolated behind a data-access interface; swappable to live sources without routing changes

### Tidal Model

- Harmonic model using M2/S2 constituents for Norman reference ports (Cherbourg, Le Havre, Saint-Malo) — sufficient precision for a ~12m vessel on short passages
- Tidal current derived from water height gradient between reference points
- Real SHOM tidal API deferred to Growth phase
- Norman coast tidal range (up to 14m near Mont-Saint-Michel bay) — tidal current is a first-class routing parameter throughout all phases

### Coastal Geometry

- Route computation requires basic bathymetric awareness: land and shallow-water obstacle detection in MVP, active avoidance in Growth

## Technical Architecture

### CLI Interface

- Single entry point: `voyageur` with named flags
- Core planning flags: `--from`, `--to`, `--depart` / `--arrive`, `--wind` (direction/speed), `--step` (minutes, default 15)
- `--boat` flag to override saved profile for a single run
- `voyageur config` subcommand to create/update persistent boat profile

### Boat Profile

- Stored at `~/.voyageur/boat.yaml` (YAML, human-editable)
- Fields: boat name, LOA, draft, sail area, polar performance model (simplified), default_step
- Loaded automatically; overridable per-run via `--boat` flag

### Routing Model

- Time-stepped isochrone propagation at configurable interval
- At each step: apply wind vector + tidal current → compute position advance → evaluate safety thresholds
- Tidal harmonic model re-evaluated at every step

### Output Format

- ASCII timeline table: one row per computation step
- Columns: elapsed time, position (lat/lon), heading, SOG, tidal current, wind
- Summary row: total distance, estimated duration, flagged decision points (tidal gates, threshold breaches)
- Output designed for standard 80-column terminal

### Data Models

| Entity | Key Fields |
|---|---|
| `BoatProfile` | name, draft, LOA, sail_area, vmg_table, default_step |
| `Route` | waypoints[], departure_time, total_duration |
| `Waypoint` | lat, lon, timestamp, heading, speed_over_ground |
| `TidalState` | timestamp, current_direction, current_speed, water_height |
| `WindCondition` | timestamp, direction, speed |

### Module Architecture

Four independent packages: `routing`, `tidal`, `cartography`, `cli` — each independently testable, each with a documented external interface to enable swapping data sources without cross-module changes.

## Functional Requirements

### Route Planning

- **FR1:** User can compute a direct route between two named Norman coast ports
- **FR2:** User can compute a route between two geographic coordinates
- **FR3:** User can specify departure time for route computation
- **FR4:** User can specify wind conditions (direction and speed) as route input
- **FR5:** User can specify the time step interval for route computation
- **FR6:** System alerts user when the direct route intersects land or shallow areas

### Tidal Model

- **FR7:** System computes tidal current (direction and speed) at any Norman coast point for a given timestamp
- **FR8:** System integrates tidal current into route calculation at each time step
- **FR9:** System displays tidal current at each step in the route timeline

### Boat Profile Management

- **FR10:** User can create and save a persistent boat profile
- **FR11:** User can update a saved boat profile
- **FR12:** System loads saved boat profile automatically at runtime
- **FR13:** User can override boat profile parameters for a single route computation

### Route Visualization & Output

- **FR14:** System displays a per-step route timeline (position, heading, SOG, wind, tidal current)
- **FR15:** System displays a passage summary: total distance, estimated duration, key decision points
- **FR16:** System alerts user when no viable route exists within safety parameters

### Condition Management

- **FR17:** User can define safety threshold parameters (max wind speed, max tidal current, max distance from nearest shelter)
- **FR18:** System evaluates each route segment against user-defined safety thresholds
- **FR19:** System flags segments where conditions approach or exceed safety thresholds

### Re-planning (Growth)

- **FR20:** User can request route re-computation from a current position and time with updated conditions
- **FR21:** System proposes alternative routes when the original route becomes unviable
- **FR22:** System notifies user when the active route is no longer safe

### Multi-Criteria Routing (Growth)

- **FR23:** System computes and presents multiple simultaneous route options per passage
- **FR24:** User can request a route optimized for fastest passage time
- **FR25:** User can request a route optimized for sailing comfort
- **FR26:** User can request a route maximizing proximity to shelter
- **FR27:** User can request a route minimizing maritime traffic exposure
- **FR28:** System suggests an optimal departure time window for a given passage

### External Data Integration (Growth)

- **FR29:** System retrieves real tidal data from an external source (SHOM API)
- **FR30:** System retrieves wind and weather forecast data from an external source
- **FR31:** System uses retrieved forecast data as route input in place of manual wind parameters

## Non-Functional Requirements

### Performance

- **NFR1:** Route computation for a Norman coast passage (< 100 NM) completes in under 5 seconds at the default 15-minute step
- **NFR2:** Route computation at 1-minute step on the same passage completes in under 30 seconds
- **NFR3:** Full timeline output fits a standard 80-column terminal without truncation for typical passages

### Integration

- **NFR4:** Tidal model module exposes a documented interface enabling replacement with SHOM API client without changes to routing module
- **NFR5:** Cartographic data layer exposes a documented interface enabling replacement with live OpenSeaMap data without changes to routing or CLI modules

### Maintainability

- **NFR6:** Each core module (`routing`, `tidal`, `cartography`, `cli`) has independent unit tests executable in isolation
- **NFR7:** Boat profile stored in human-readable YAML or JSON, editable without a dedicated tool
- **NFR8:** Codebase follows PEP 8 conventions throughout
