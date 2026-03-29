---
project_name: 'voyageur'
user_name: 'JC'
date: '2026-03-29'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
status: 'complete'
rule_count: 64
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Python**: 3.11+ (use match statements, typing.Protocol, dataclasses with slots)
- **CLI framework**: Typer (flags declared as typed function parameters — no argparse)
- **Packaging**: Poetry / pyproject.toml (no setup.py, no requirements.txt)
- **Testing**: pytest (no unittest)
- **Linting/Formatting**: ruff (replaces flake8 + black — single tool, single config in pyproject.toml)
- **Geospatial**: pyproj (geodesic calculations on WGS84 ellipsoid), shapely (2D geometry)
- **Data format**: YAML for boat profile and tidal constants, GeoJSON for cartographic data (both embedded in package)

## Critical Implementation Rules

### Language-Specific Rules

- All domain objects MUST be `@dataclass` — never plain `dict` for inter-module data exchange
- Use `typing.Protocol` for module interfaces; define protocol in `protocol.py` BEFORE writing `impl.py`
- All shared dataclasses live in `voyageur/models.py` — no duplicate class definitions in other modules
- Type-annotate all function signatures; no bare `Any`
- `datetime` objects must be timezone-aware (`datetime.timezone.utc`) — all timestamps in UTC
- Coordinate system: WGS84 lat/lon floats everywhere — never degrees+minutes+seconds strings internally
- Constants: `UPPER_SNAKE_CASE` at module level (e.g., `DEFAULT_STEP_MINUTES = 15`)

### Framework-Specific Rules (Typer CLI)

- All CLI flags: `--kebab-case` without exception — Typer converts `snake_case` params to `--kebab-case` automatically
- Wind input format: `"240/15"` (direction°/speed kn) — validate with regex `^\d{1,3}/\d+(\.\d+)?$`
- Position input format: `"49.65N/1.62W"` — parse to `(float, float)` immediately on input
- Departure time: ISO 8601 string `"2026-03-29T08:00"` — parse to timezone-aware `datetime` immediately
- ALL output goes through `typer.echo()` — NEVER use `print()`
- Route timeline → stdout; all alerts and errors → stderr (`typer.echo(msg, err=True)`)
- User-facing errors: `typer.echo(msg, err=True)` then `raise typer.Exit(1)` — never `sys.exit()`
- Warning prefix: `⚠` (continues execution); blocking error prefix: `✗` (exits 1)
- `voyageur config` is a Typer subcommand (`app.add_typer(config_app, name="config")`)

### Testing Rules

- All tests in `tests/` directory — NEVER co-locate tests with source code
- Test file naming: `test_<module>.py` mirroring `voyageur/<module>/` (e.g., `tests/test_tidal.py`)
- Shared fixtures in `tests/conftest.py` — never duplicate fixtures across test files
- Use mock `TidalProvider` and `CartographyProvider` in routing tests — inject via constructor, never patch
- Test each module in isolation: `test_tidal.py` imports only from `voyageur.tidal`, never from `voyageur.routing`
- Performance tests: use `time.perf_counter()` directly in test — no special benchmark library needed for NFR1/2
- No `unittest.mock.patch` for module-level state — prefer dependency injection (Protocol-based)
- Minimum: one happy-path test + one error-path test per public function

### Code Quality & Style Rules

- Naming: functions/variables `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`, files `snake_case`
- ruff configured in `pyproject.toml` — run `make lint` before any commit; zero tolerance for violations
- No docstrings required on private/internal functions; public module interfaces should have one-line docstrings
- 80-column hard limit for CLI output only (NFR3) — source code lines may exceed 80 chars (ruff default: 88)
- Module internal structure ALWAYS: `__init__.py` + `protocol.py` + `impl.py` for data-providing modules
- `voyageur/models.py` is the single source of truth for all dataclasses — if you need a new shared type, add it there
- No relative imports across module boundaries — always use `from voyageur.models import ...`
- YAML files use 2-space indentation; GeoJSON is minified (no pretty-print for embedded data)

### Development Workflow Rules

- Install: `poetry install` — never `pip install` directly in the project
- Run tests: `make test` (`poetry run pytest tests/ -v`)
- Lint: `make lint` (`poetry run ruff check voyageur/ tests/`)
- Format: `make format` (`poetry run ruff format voyageur/ tests/`)
- Clean: `make clean` (removes `__pycache__` directories)
- Boat profile stored at `~/.voyageur/boat.yaml` — create `~/.voyageur/` if absent, never fail silently
- Embedded data files (`ports.yaml`, `normandy.geojson`) read via `importlib.resources` — never hardcoded absolute paths
- No CI/CD in MVP — local `make test && make lint` is the quality gate

### Critical Don't-Miss Rules

**Anti-patterns to avoid:**
- ❌ `print(...)` — use `typer.echo()` everywhere
- ❌ `routing.get_current({"lat": 49.0})` — use dataclasses, never dicts for domain objects
- ❌ `def get_TidalCurrent()` — mixed case in function names
- ❌ `--departureTime` — camelCase CLI flags
- ❌ Importing concrete `HarmonicTidalModel` in `routing/` — only import `TidalProvider` protocol
- ❌ Defining `Waypoint` or `Route` in any file other than `voyageur/models.py`
- ❌ Naive `datetime.now()` — always `datetime.now(timezone.utc)` for timestamps
- ❌ Hardcoded file paths like `/home/user/.voyageur/` — use `pathlib.Path.home() / ".voyageur"`

**Critical edge cases:**
- Departure arriving at destination within first step: check distance ≤ tolerance before loop starts
- Step size of 1 min on 100 NM passage = ~600 steps — algorithm must be O(n), no nested loops
- Norman coast tidal current can reach 5+ kn (Raz Blanchard) — do not clamp or filter extreme values
- `--wind 0/0` (no wind, no motor) is a valid input — handle zero-speed propagation gracefully
- Port name lookup is case-insensitive: `"cherbourg"` == `"Cherbourg"` == `"CHERBOURG"`

**Time dimension (cross-cutting concern):**
- Every computation step is a `(position, timestamp)` pair — never position alone
- `TidalProvider.get_current()` is called at EVERY step with the current timestamp — not once at departure
- `--step` propagates to routing, tidal evaluation, and output simultaneously

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — no exceptions
- When in doubt, prefer the more restrictive option
- Module boundaries are strict: `routing/` never imports from `tidal/impl.py` directly

**For Humans:**

- Keep this file lean and focused on agent needs
- Update when technology stack or conventions change
- Remove rules that become obvious over time

Last Updated: 2026-03-29
