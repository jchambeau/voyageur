# Story 1.3: Module Interface Protocols

Status: done

## Story

As a developer,
I want `TidalProvider` and `CartographyProvider` defined as `typing.Protocol`,
So that the routing module can be written and tested with mock implementations, independently of the concrete tidal and cartography modules.

## Acceptance Criteria

1. `TidalProvider` est importable depuis `voyageur.tidal.protocol` et définit `get_current(self, lat: float, lon: float, at: datetime.datetime) -> TidalState`
2. `CartographyProvider` est importable depuis `voyageur.cartography.protocol` et définit `intersects_land(self, route: list[Waypoint]) -> bool`
3. Une classe mock minimale implémentant chaque protocol satisfait `isinstance(mock, TidalProvider)` / `isinstance(mock, CartographyProvider)` via la vérification structurelle de `Protocol`
4. `tests/test_protocols.py` passe — mock compliance vérifiée pour les deux protocols
5. `poetry run ruff check voyageur/ tests/` signale zéro violation

## Tasks / Subtasks

- [x] Créer `voyageur/tidal/protocol.py` (AC: 1, 3)
  - [x] Importer `datetime`, `Protocol`, `runtime_checkable` depuis stdlib
  - [x] Importer `TidalState` depuis `voyageur.models`
  - [x] Définir `TidalProvider` avec `@runtime_checkable` et méthode `get_current`

- [x] Créer `voyageur/cartography/protocol.py` (AC: 2, 3)
  - [x] Importer `Protocol`, `runtime_checkable` depuis stdlib
  - [x] Importer `Waypoint` depuis `voyageur.models`
  - [x] Définir `CartographyProvider` avec `@runtime_checkable` et méthode `intersects_land`

- [x] Créer `tests/test_protocols.py` (AC: 3, 4)
  - [x] Mock `MockTidalProvider` — implémente `get_current`, passe `isinstance`
  - [x] Mock `MockCartographyProvider` — implémente `intersects_land`, passe `isinstance`
  - [x] Tester que les mocks satisfont bien le Protocol structurel
  - [x] Tester que les signatures de méthodes sont correctes (appel effectif)

- [x] Valider les critères d'acceptation (AC: 5)
  - [x] `poetry run ruff check voyageur/ tests/` exit 0
  - [x] `poetry run pytest tests/ -v` exit 0 (13/13 tests passent)

## Dev Notes

### Critical: `@runtime_checkable` est OBLIGATOIRE

Sans `@runtime_checkable`, `isinstance(mock, TidalProvider)` lève `TypeError` à l'exécution. Ce décorateur est indispensable pour que l'AC 3 fonctionne.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TidalProvider(Protocol):
    ...
```

### Critical: Implémentation exacte de `voyageur/tidal/protocol.py`

```python
import datetime
from typing import Protocol, runtime_checkable

from voyageur.models import TidalState


@runtime_checkable
class TidalProvider(Protocol):
    """Interface for tidal data providers."""

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState: ...
```

### Critical: Implémentation exacte de `voyageur/cartography/protocol.py`

```python
from typing import Protocol, runtime_checkable

from voyageur.models import Waypoint


@runtime_checkable
class CartographyProvider(Protocol):
    """Interface for cartographic data providers."""

    def intersects_land(self, route: list[Waypoint]) -> bool: ...
```

### Critical: Import `datetime` comme module

La règle project-context est : `import datetime` (jamais `from datetime import datetime`). Le paramètre `at` doit être annoté `datetime.datetime`, pas `datetime`.

### Critical: Séparation des imports pour ruff I001

ruff enforce une ligne vide entre les groupes stdlib et first-party :

```python
import datetime                              # stdlib
from typing import Protocol, runtime_checkable  # stdlib (même groupe)
                                             # ← ligne vide obligatoire
from voyageur.models import TidalState       # first-party
```

### Critical: Fichiers existants à NE PAS modifier

- `voyageur/tidal/__init__.py` — stub existant, NE PAS toucher
- `voyageur/cartography/__init__.py` — stub existant, NE PAS toucher
- `voyageur/tidal/impl.py` — N'EXISTE PAS encore (Story 2.1)
- `voyageur/cartography/impl.py` — N'EXISTE PAS encore (Stories 2.1 / 3.1)

Cette story crée UNIQUEMENT :
- `voyageur/tidal/protocol.py` (nouveau)
- `voyageur/cartography/protocol.py` (nouveau)
- `tests/test_protocols.py` (nouveau)

### Critical: Structure exacte de `tests/test_protocols.py`

```python
"""Tests for TidalProvider and CartographyProvider Protocol compliance."""
import datetime

import pytest

from voyageur.cartography.protocol import CartographyProvider
from voyageur.models import TidalState, Waypoint
from voyageur.tidal.protocol import TidalProvider


class MockTidalProvider:
    """Minimal mock implementing TidalProvider structurally."""

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        return TidalState(
            timestamp=at,
            current_direction=90.0,
            current_speed=1.5,
            water_height=3.0,
        )


class MockCartographyProvider:
    """Minimal mock implementing CartographyProvider structurally."""

    def intersects_land(self, route: list[Waypoint]) -> bool:
        return False


def test_tidal_provider_isinstance() -> None:
    assert isinstance(MockTidalProvider(), TidalProvider)


def test_cartography_provider_isinstance() -> None:
    assert isinstance(MockCartographyProvider(), CartographyProvider)


def test_tidal_provider_get_current(now: datetime.datetime) -> None:
    provider = MockTidalProvider()
    result = provider.get_current(lat=49.65, lon=-1.62, at=now)
    assert isinstance(result, TidalState)
    assert result.timestamp == now


def test_cartography_provider_intersects_land(now: datetime.datetime) -> None:
    provider = MockCartographyProvider()
    wp = Waypoint(lat=49.65, lon=-1.62, timestamp=now, heading=180.0, speed_over_ground=5.0)
    result = provider.intersects_land(route=[wp])
    assert result is False
```

### Critical: make n'est pas installé

Valider via :
```bash
export PATH="$HOME/.local/bin:$PATH"
poetry run ruff check voyageur/ tests/
poetry run pytest tests/ -v
```

### Learnings des stories précédentes

**Story 1.1 :**
- `export PATH="$HOME/.local/bin:$PATH"` avant toute commande poetry
- ruff I001 : ligne vide obligatoire entre les groupes d'imports stdlib / third-party / first-party

**Story 1.2 :**
- Fixture `now: datetime.datetime` disponible dans `tests/conftest.py` — utiliser comme paramètre de fonction de test
- `@dataclass(slots=True)` requis sur les dataclasses (non applicable ici — Protocol n'est pas un dataclass)
- Import `datetime` comme module — `datetime.datetime` partout

### Conformité architectural

- `voyageur.tidal.protocol` et `voyageur.cartography.protocol` sont les seuls modules autorisés à définir ces interfaces
- Le module `routing` ne devra JAMAIS importer depuis `tidal/impl.py` ou `cartography/impl.py` — uniquement depuis les `protocol.py`
- Les Protocols ici définissent le **contrat** ; l'implémentation concrète (`HarmonicTidalModel`) est Story 2.1

## Review Findings

- [x] [Review][Patch] Docstrings manquantes sur les méthodes Protocol — fixed: docstrings ajoutées sur `get_current` et `intersects_land` [voyageur/tidal/protocol.py, voyageur/cartography/protocol.py]
- [x] [Review][Patch] `test_tidal_provider_get_current` n'assert que `timestamp` — fixed: assertions ajoutées sur `current_direction`, `current_speed`, `water_height` [tests/test_protocols.py]

- [x] [Review][Defer] `@runtime_checkable` vérifie seulement l'existence du nom de méthode, pas la signature — deferred, pre-existing; limitation Python, détection complète = mypy/pyright (hors scope MVP)
- [x] [Review][Defer] Datetime naive accepté au niveau Protocol sans guard — deferred, pre-existing; carryover Story 1.2, validation = frontière CLI (Story 2.4)
- [x] [Review][Defer] `intersects_land` avec route vide non testée — deferred, pre-existing; comportement sur liste vide = Story 3.1 (implémentation cartographie)
- [x] [Review][Defer] Risque d'évolution Protocol (nouvelle méthode casse les implémenteurs existants) — deferred, pre-existing; concern architectural hors scope MVP
- [x] [Review][Defer] Chemin `True` de `intersects_land` non couvert par les tests Protocol — deferred, pre-existing; tests de comportement = Stories 2.2/3.1

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Completion Notes List

- `voyageur/tidal/protocol.py` : `TidalProvider` avec `@runtime_checkable`, méthode `get_current(lat, lon, at) -> TidalState`
- `voyageur/cartography/protocol.py` : `CartographyProvider` avec `@runtime_checkable`, méthode `intersects_land(route) -> bool`
- `tests/test_protocols.py` : 4 tests — isinstance check pour chaque Protocol + appel effectif des méthodes
- Fixture `now` depuis conftest.py utilisée dans les tests
- 13/13 tests passent, ruff propre (0 violations)

### File List

- `voyageur/tidal/protocol.py`
- `voyageur/cartography/protocol.py`
- `tests/test_protocols.py`
