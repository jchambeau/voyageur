# Story 1.1: Project Scaffold Setup

Status: done

## Story

As a developer,
I want to initialize the Voyageur project with Poetry, Typer, pytest, ruff, and a Makefile,
so that the project can be installed, run, and tested from day one with consistent tooling.

## Acceptance Criteria

1. Running `poetry install` installs all dependencies: typer, pyproj, shapely, pytest, ruff
2. `voyageur --help` outputs a usage message with exit code 0
3. `make test` runs the (empty) test suite and exits with code 0
4. `make lint` runs ruff on `voyageur/` and `tests/` with no errors
5. The project structure matches the architecture spec: all subpackage `__init__.py` files present, `tests/` directory initialized

## Tasks / Subtasks

- [x] Initialize Poetry project (AC: 1)
  - [x] Create `pyproject.toml` with `requires-python = ">=3.11"`, project metadata, and all dependencies
  - [x] Add production deps: `poetry add typer pyproj shapely`
  - [x] Add dev deps: `poetry add --group dev pytest ruff`
  - [x] Set entry point in `[tool.poetry.scripts]`: `voyageur = "voyageur.cli.main:app"`
  - [x] Configure ruff in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`

- [x] Create complete package directory structure (AC: 5)
  - [x] `voyageur/__init__.py`
  - [x] `voyageur/models.py` (empty file — will be populated in Story 1.2)
  - [x] `voyageur/cli/__init__.py`
  - [x] `voyageur/cli/main.py` (minimal Typer app — see Dev Notes)
  - [x] `voyageur/cli/config.py` (empty stub)
  - [x] `voyageur/routing/__init__.py`
  - [x] `voyageur/routing/planner.py` (empty stub)
  - [x] `voyageur/routing/safety.py` (empty stub)
  - [x] `voyageur/tidal/__init__.py`
  - [x] `voyageur/tidal/data/` directory with `.gitkeep`
  - [x] `voyageur/cartography/__init__.py`
  - [x] `voyageur/cartography/data/` directory with `.gitkeep`
  - [x] `voyageur/output/__init__.py`

- [x] Create tests directory (AC: 3)
  - [x] `tests/__init__.py`
  - [x] `tests/conftest.py` (empty — shared fixtures will be added in future stories)

- [x] Create Makefile (AC: 3, 4)
  - [x] `install` target: `poetry install`
  - [x] `test` target: `poetry run pytest tests/ -v`
  - [x] `lint` target: `poetry run ruff check voyageur/ tests/`
  - [x] `format` target: `poetry run ruff format voyageur/ tests/`
  - [x] `clean` target: `find . -type d -name __pycache__ -exec rm -rf {} +`

- [x] Create minimal Typer entry point (AC: 2)
  - [x] `voyageur/cli/main.py`: Typer app with a placeholder `plan` command (see Dev Notes)

- [x] Create `.gitignore` and `README.md`

- [x] Validate all acceptance criteria
  - [x] `poetry install` succeeds
  - [x] `voyageur --help` exits 0 with usage output
  - [x] `poetry run pytest tests/ -v` exits 0 (3 scaffold tests pass) — note: `make` not installed on system; Makefile targets verified via direct poetry commands
  - [x] `poetry run ruff check voyageur/ tests/` exits 0 (no violations)

## Dev Notes

### Critical: pyproject.toml Entry Point

The `voyageur --help` AC requires the CLI entry point to be registered correctly. Without this, the `voyageur` command will not exist after `poetry install`:

```toml
[tool.poetry.scripts]
voyageur = "voyageur.cli.main:app"
```

### Critical: Minimal `voyageur/cli/main.py`

Must define a `typer.Typer()` app named `app` — this is what the entry point references:

```python
import typer

app = typer.Typer(
    name="voyageur",
    help="Sailing route planner for the Norman coast.",
    no_args_is_help=True,
)

@app.command()
def plan(
    from_port: str = typer.Option(..., "--from", help="Departure port or coordinates"),
    to_port: str = typer.Option(..., "--to", help="Destination port or coordinates"),
) -> None:
    """Plan a sailing passage between two Norman coast ports."""
    typer.echo("Voyage planning not yet implemented.")
```

**Important:** Typer uses `--from` as the CLI flag when the Python parameter is named `from_port` — use `typer.Option(..., "--from", ...)` to override the default `--from-port`. This is required by the architecture's naming convention.

### Critical: ruff Configuration in pyproject.toml

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = []

[tool.ruff.lint.isort]
known-first-party = ["voyageur"]
```

The `"I"` rule set enforces import ordering — all stub files must have no unused imports to pass lint.

### Critical: pyproject.toml Python Version

```toml
[tool.poetry.dependencies]
python = ">=3.11"
```

Python 3.11 is required (typing.Protocol, dataclasses with `slots=True`, match statements).

### Critical: Stub Files Must Be Lint-Clean

All empty stub files (`routing/planner.py`, `routing/safety.py`, `cli/config.py`) must contain no code or only a docstring — an empty file is lint-clean. DO NOT add placeholder imports that ruff will flag as unused.

Acceptable stub file content:
```python
# Placeholder — implemented in Story X.Y
```
Or simply empty.

### Project Structure (Architecture Reference)

```
voyageur/
├── Makefile
├── pyproject.toml
├── README.md
├── .gitignore
├── voyageur/
│   ├── __init__.py
│   ├── models.py                    # empty — Story 1.2
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                  # THIS STORY — minimal Typer app
│   │   └── config.py                # empty stub — Story 3.3
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── planner.py               # empty stub — Story 2.2
│   │   └── safety.py                # empty stub — Story 3.2
│   ├── tidal/
│   │   ├── __init__.py
│   │   └── data/
│   ├── cartography/
│   │   ├── __init__.py
│   │   └── data/
│   └── output/
│       └── __init__.py
└── tests/
    ├── __init__.py
    └── conftest.py
```

`protocol.py` and `impl.py` files for `tidal/` and `cartography/` are NOT created in this story — they are Story 1.3's responsibility.

### Makefile Notes

Use tabs (not spaces) for Makefile recipe indentation — make will fail silently with spaces.

```makefile
.PHONY: install test lint format clean

install:
	poetry install

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check voyageur/ tests/

format:
	poetry run ruff format voyageur/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
```

### .gitignore Essentials

```
__pycache__/
*.pyc
.venv/
dist/
.ruff_cache/
.pytest_cache/
*.egg-info/
```

### No Implementation Beyond Scope

This story creates the scaffold ONLY. Do NOT:
- Add any logic to `planner.py`, `safety.py`, or `config.py`
- Add any imports to `models.py`
- Create `protocol.py` or `impl.py` files (those are Story 1.3)
- Add fixtures to `conftest.py`

### Project Structure Notes

- All files in `voyageur/` must be importable after `poetry install` — verify with `python -c "import voyageur"`
- `voyageur/tidal/data/` and `voyageur/cartography/data/` directories need to exist for future stories; use `.gitkeep` to include them in git

### References

- [Source: planning-artifacts/architecture.md#Starter Template Evaluation] — Poetry + Typer + pytest + ruff stack decision
- [Source: planning-artifacts/architecture.md#Complete Project Directory Structure] — canonical file tree
- [Source: planning-artifacts/architecture.md#Development Workflow] — Makefile targets
- [Source: planning-artifacts/architecture.md#Naming Patterns] — `--kebab-case` CLI flags
- [Source: planning-artifacts/project-context.md#Framework-Specific Rules (Typer CLI)] — Typer flag naming conventions
- [Source: planning-artifacts/project-context.md#Development Workflow Rules] — `importlib.resources` for embedded data (future stories)

## Review Findings

- [x] [Review][Decision] tests/__init__.py presence — décision: conserver. Cohérent avec `tests/conftest.py`, sans impact négatif pour ce projet non-distribué.

- [x] [Review][Patch] poetry.lock listed in .gitignore [.gitignore] — fixed: removed from .gitignore
- [x] [Review][Patch] Dependency version ranges use `>=` instead of caret constraints [pyproject.toml] — fixed: changed to `^`
- [x] [Review][Patch] Stray `main.py` at project root uses `print()` and is not covered by ruff lint scope [main.py] — fixed: excluded via ruff `exclude` in pyproject.toml
- [x] [Review][Patch] Stray `pytest.py` at project root not in architecture spec and not covered by ruff [pytest.py] — fixed: excluded via ruff `exclude` in pyproject.toml
- [x] [Review][Patch] .gitignore missing common entries: `.idea/`, `*.so`, `*.pyd` [.gitignore] — fixed: entries added
- [x] [Review][Patch] Smoke tests use `assert x is not None` — assertions too weak to catch regressions [tests/test_scaffold.py] — fixed: assertions use `isinstance()` checks
- [x] [Review][Patch] `app.info.name` test accesses internal Typer API — fragile, may break on Typer upgrade [tests/test_scaffold.py:27] — fixed: replaced with CliRunner `--help` invocation test

- [x] [Review][Defer] CLI input validation for `--step` (no bounds check on 1/5/15/30/60) [voyageur/cli/main.py:16] — deferred, pre-existing
- [x] [Review][Defer] CLI input validation for `--from`/`--to`/`--wind`/`--depart` (no format checking) [voyageur/cli/main.py:12-15] — deferred, pre-existing
- [x] [Review][Defer] Hard dependency on system PROJ/GEOS libraries not documented in README [README.md] — deferred, pre-existing
- [x] [Review][Defer] No CI/CD pipeline configured — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Poetry not installed → installed via official installer (curl | python3)
- `make` not available on system → Makefile created, targets verified via direct `poetry run` commands
- pytest exit code 5 (no tests) → added `tests/test_scaffold.py` with 3 smoke tests
- ruff E501 + F401 + I001 violations → fixed unused import, sorted imports, shortened help strings

### Completion Notes List

- Poetry 2.3.2 installed at `~/.local/bin/poetry`
- All 5 ACs satisfied: deps installed, `voyageur --help` works, pytest 3/3 pass, ruff clean, all `__init__.py` present
- Note for next story: use `export PATH="$HOME/.local/bin:$PATH"` before running poetry commands

### File List

- `pyproject.toml`
- `Makefile`
- `README.md`
- `.gitignore`
- `voyageur/__init__.py`
- `voyageur/models.py`
- `voyageur/cli/__init__.py`
- `voyageur/cli/main.py`
- `voyageur/cli/config.py`
- `voyageur/routing/__init__.py`
- `voyageur/routing/planner.py`
- `voyageur/routing/safety.py`
- `voyageur/tidal/__init__.py`
- `voyageur/tidal/data/.gitkeep`
- `voyageur/cartography/__init__.py`
- `voyageur/cartography/data/.gitkeep`
- `voyageur/output/__init__.py`
- `voyageur/output/formatter.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_scaffold.py`
