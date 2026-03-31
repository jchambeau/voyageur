# Story 5.1: SHOM Tidal API Client

Status: review

## Story

As JC,
I want the system to retrieve real tidal data from the SHOM API instead of the embedded harmonic model,
so that my route calculations use authoritative French hydrographic data without any manual input.

## Acceptance Criteria

1. Given a valid SHOM API key stored under key `shom_api_key` in `~/.voyageur/config.yaml`, when `voyageur plan` (or `replan`) is run, then the system instantiates `ShomTidalClient` instead of `HarmonicTidalModel`
2. `ShomTidalClient.get_current(lat, lon, at)` queries the SHOM API and returns a valid `TidalState` (timestamp, current_direction ∈ [0, 360), current_speed ≥ 0, water_height any float)
3. `ShomTidalClient` satisfies the `TidalProvider` protocol — `isinstance(ShomTidalClient(...), TidalProvider)` is True — and the routing module requires no changes (NFR4)
4. If the SHOM API is unavailable (network error, non-2xx response, JSON parse error), the system falls back to `HarmonicTidalModel` and emits `⚠ SHOM API unavailable — using embedded harmonic model` to stderr
5. `tests/test_tidal.py` passes: `ShomTidalClient` tested with injected mock HTTP client — happy path returns `TidalState`; fallback path (HTTP error) returns `TidalState` from harmonic model
6. `poetry run ruff check voyageur/ tests/` returns zero violations

## Tasks / Subtasks

- [x] Ajouter `httpx` à `pyproject.toml` (AC: 2)
  - [x] `poetry add "httpx>=0.27"` — dépendance runtime (pas dev)
  - [x] Vérifier que `poetry install` réussit sans conflits

- [x] Créer `voyageur/tidal/shom_client.py` — `ShomTidalClient` (AC: 2, 3, 4)
  - [x] Constante module : `SHOM_API_URL = "https://services.data.shom.fr/hdm/tidal/current"` (overridable via sous-classe)
  - [x] Classe `ShomTidalClient` avec `__init__(self, api_key: str, fallback: TidalProvider | None = None, http_client: httpx.Client | None = None)`
    - [x] `self._api_key = api_key`
    - [x] `self._fallback: TidalProvider = fallback or HarmonicTidalModel()`
    - [x] `self._http = http_client or httpx.Client(timeout=10.0)`
  - [x] Méthode `get_current(lat, lon, at) -> TidalState` :
    - [x] Requête `GET SHOM_API_URL` avec params `lat`, `lon`, `datetime=at.isoformat()`, `apikey=self._api_key`
    - [x] `resp.raise_for_status()`
    - [x] Parser `data = resp.json()` → `TidalState(timestamp=at, current_direction=float(data["direction"]), current_speed=float(data["speed"]), water_height=float(data.get("height", 0.0)))`
    - [x] `except Exception` → `sys.stderr.write("⚠ SHOM API unavailable — using embedded harmonic model\n")` + `return self._fallback.get_current(lat, lon, at)`

- [x] Modifier `voyageur/cli/main.py` — sélection du provider tidal (AC: 1)
  - [x] Ajouter `import pathlib` en tête de fichier si absent (vérifier — déjà présent en import local dans `_load_boat`)
  - [x] Ajouter fonction module-level `_load_voyageur_config() -> dict` : lit `~/.voyageur/config.yaml` via `yaml.safe_load`, retourne `{}` si absent ou corrompu
  - [x] Ajouter fonction module-level `_build_tidal_provider()` : retourne `ShomTidalClient(api_key)` si `shom_api_key` ∈ config, sinon `HarmonicTidalModel()` (imports lazy à l'intérieur)
  - [x] Remplacer les deux occurrences `tidal = HarmonicTidalModel()` (dans `plan()` et `replan()`) par `tidal = _build_tidal_provider()`
  - [x] Supprimer `from voyageur.tidal.impl import HarmonicTidalModel` des imports lazy (déplacé dans `_build_tidal_provider`)

- [x] Modifier `tests/test_tidal.py` — nouveaux tests `ShomTidalClient` (AC: 5)
  - [x] Définir localement `_MockHttpClient` et `_MockHttpResponse` pour injection (pas de patching)
    - [x] `_MockHttpResponse(data: dict)` : `.raise_for_status()` no-op, `.json()` retourne `data`
    - [x] `_MockHttpClient(response_data: dict | None, raise_error: Exception | None = None)` : `.get(url, **kwargs)` retourne `_MockHttpResponse(data)` ou lève l'exception
  - [x] `test_shom_client_satisfies_protocol` : `isinstance(ShomTidalClient("key"), TidalProvider)` → True
  - [x] `test_shom_client_happy_path` : mock retourne `{"direction": 180.0, "speed": 2.3, "height": 3.5}` → vérifier `result.current_direction == 180.0`, `result.current_speed == 2.3`, `result.water_height == 3.5`
  - [x] `test_shom_client_fallback_on_error` : mock lève `Exception("timeout")` → vérifier résultat est un `TidalState` (provient du harmonic model) + vérifier `capsys.readouterr().err` contient `"⚠ SHOM API unavailable"`

- [x] Valider (AC: 6)
  - [x] `poetry run ruff check voyageur/ tests/`
  - [x] `poetry run pytest tests/ -v`

## Dev Notes

### 1. Nouveau fichier : `voyageur/tidal/shom_client.py`

```python
import sys
import datetime

import httpx

from voyageur.models import TidalState
from voyageur.tidal.impl import HarmonicTidalModel
from voyageur.tidal.protocol import TidalProvider

SHOM_API_URL: str = "https://services.data.shom.fr/hdm/tidal/current"


class ShomTidalClient:
    """TidalProvider that queries the SHOM API with HarmonicTidalModel fallback."""

    def __init__(
        self,
        api_key: str,
        fallback: TidalProvider | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._fallback: TidalProvider = fallback or HarmonicTidalModel()
        self._http = http_client or httpx.Client(timeout=10.0)

    def get_current(
        self, lat: float, lon: float, at: datetime.datetime
    ) -> TidalState:
        """Return tidal state from SHOM API; fallback to harmonic model on error."""
        try:
            resp = self._http.get(
                SHOM_API_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "datetime": at.isoformat(),
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return TidalState(
                timestamp=at,
                current_direction=float(data["direction"]),
                current_speed=float(data["speed"]),
                water_height=float(data.get("height", 0.0)),
            )
        except Exception:
            sys.stderr.write(
                "⚠ SHOM API unavailable — using embedded harmonic model\n"
            )
            return self._fallback.get_current(lat, lon, at)
```

**Note sur l'API SHOM** : L'endpoint `SHOM_API_URL` est un design plausible à partir de la documentation publique SHOM. À vérifier contre la documentation officielle `data.shom.fr` avant utilisation en production. La réponse attendue est `{"direction": float, "speed": float, "height": float}`.

### 2. Import `HarmonicTidalModel` dans `shom_client.py`

Le `ShomTidalClient` importe directement `HarmonicTidalModel` pour le fallback. C'est l'une des rares exceptions où `tidal/shom_client.py` importe depuis `tidal/impl.py` — acceptable car les deux sont dans le même module `tidal/`. La règle "routing ne doit pas importer `impl.py` directement" s'applique au module `routing/`, pas à l'intérieur de `tidal/`.

### 3. `_load_voyageur_config()` dans `cli/main.py`

```python
def _load_voyageur_config() -> dict:
    """Load ~/.voyageur/config.yaml; return {} if absent or corrupt."""
    import pathlib
    import yaml
    path = pathlib.Path.home() / ".voyageur" / "config.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
```

`pathlib` est déjà dans la stdlib — pas de dépendance à ajouter. `yaml` est déjà importé au niveau module dans `cli/config.py` mais PAS dans `cli/main.py` — utiliser un import local dans la fonction pour éviter un import circulaire ou une pollution du module.

### 4. `_build_tidal_provider()` dans `cli/main.py`

```python
def _build_tidal_provider():
    """Return ShomTidalClient if shom_api_key configured, else HarmonicTidalModel."""
    from voyageur.tidal.impl import HarmonicTidalModel
    from voyageur.tidal.shom_client import ShomTidalClient

    config = _load_voyageur_config()
    api_key = config.get("shom_api_key")
    if api_key:
        return ShomTidalClient(api_key=api_key)
    return HarmonicTidalModel()
```

Placer après les fonctions `_parse_*` existantes, avant `plan()`. Retirer `from voyageur.tidal.impl import HarmonicTidalModel` des blocs lazy imports dans `plan()` et `replan()` — remplacé par `_build_tidal_provider()`.

### 5. Remplacement dans `plan()` et `replan()`

Chercher et remplacer :
```python
# AVANT (plan(), ~ligne 284 + 310)
from voyageur.tidal.impl import HarmonicTidalModel
...
tidal = HarmonicTidalModel()

# APRÈS
tidal = _build_tidal_provider()
```

Même remplacement dans `replan()` (~ligne 499 + 526). L'import `HarmonicTidalModel` devient superflu dans `plan()` / `replan()` — le supprimer.

### 6. Tests — mocks locaux dans `test_tidal.py`

```python
class _MockHttpResponse:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._data


class _MockHttpClient:
    def __init__(
        self,
        response_data: dict | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self._data = response_data
        self._raise = raise_error

    def get(self, url: str, **kwargs) -> _MockHttpResponse:
        if self._raise is not None:
            raise self._raise
        return _MockHttpResponse(self._data or {})
```

Utiliser ces mocks via injection dans le constructeur — pas de `unittest.mock.patch`.

### 7. Test happy path

```python
def test_shom_client_happy_path(now: datetime.datetime) -> None:
    client = ShomTidalClient(
        api_key="test-key",
        http_client=_MockHttpClient(
            response_data={"direction": 180.0, "speed": 2.3, "height": 3.5}
        ),
    )
    result = client.get_current(lat=49.6453, lon=-1.6222, at=now)
    assert result.current_direction == 180.0
    assert result.current_speed == 2.3
    assert result.water_height == 3.5
    assert result.timestamp == now
```

### 8. Test fallback

```python
def test_shom_client_fallback_on_error(now: datetime.datetime, capsys) -> None:
    client = ShomTidalClient(
        api_key="test-key",
        http_client=_MockHttpClient(raise_error=Exception("timeout")),
    )
    result = client.get_current(lat=49.6453, lon=-1.6222, at=now)
    assert isinstance(result, TidalState)
    assert result.current_speed >= 0.0
    captured = capsys.readouterr()
    assert "⚠ SHOM API unavailable" in captured.err
```

### 9. `~/.voyageur/config.yaml` format attendu

```yaml
shom_api_key: "your-api-key-here"
```

Aucun changement à `voyageur config` n'est requis pour cette story — l'utilisateur édite `config.yaml` manuellement. Support CLI (`voyageur config --shom-api-key`) = Story 5.x si besoin.

### 10. `pathlib` dans `cli/main.py`

Vérifier si `import pathlib` est déjà présent au niveau module dans `main.py`. La story 3.3 a ajouté `pathlib` dans `cli/config.py` — mais `cli/main.py` n'a peut-être pas l'import. `_load_voyageur_config()` utilise un import local pour éviter tout problème.

### 11. `httpx.Client` lifetime

`httpx.Client` doit idéalement être fermé (`.close()` ou context manager `with`). Pour MVP, instancié une seule fois dans `_build_tidal_provider()` et passé au constructeur — la durée de vie = celle du process CLI. Pas de gestion de fermeture explicite pour MVP.

### 12. Fichiers à modifier/créer

| Action | Fichier |
|--------|---------|
| Créer | `voyageur/tidal/shom_client.py` |
| Modifier | `pyproject.toml` — ajouter `httpx>=0.27` |
| Modifier | `voyageur/cli/main.py` — `_load_voyageur_config()`, `_build_tidal_provider()`, remplacer `tidal = HarmonicTidalModel()` |
| Modifier | `tests/test_tidal.py` — 3 nouveaux tests + mocks locaux |

### 13. Fichiers à NE PAS toucher

- `voyageur/tidal/protocol.py` — `TidalProvider` protocol inchangé (NFR4)
- `voyageur/tidal/impl.py` — `HarmonicTidalModel` inchangé
- `voyageur/routing/` — aucun changement (NFR4)
- `voyageur/models.py` — `TidalState` inchangé
- `tests/conftest.py` — ne pas y ajouter de mocks SHOM

### 14. Nouvelle dépendance `httpx`

`httpx` est une dépendance runtime (pas dev). L'ajouter avec `poetry add "httpx>=0.27"`. Vérifier la compatibilité avec Python 3.11+ (httpx >= 0.27 supporte Python 3.8+).

### 15. Apprentissages stories précédentes

**Story 4.3 :**
- Imports lazy dans `plan()` → factoriser via une fonction module-level `_build_*` est plus propre
- Ruff 88 chars — surveiller les lignes longues dans `_load_voyageur_config()`

**Story 1.3 (protocols) :**
- `@runtime_checkable` + `isinstance(ShomTidalClient(...), TidalProvider)` fonctionne si toutes les méthodes du protocol sont définies avec la bonne arité

**Story 2.1 (harmonic tidal) :**
- `importlib.resources` pour les données embarquées — pas pertinent ici (SHOM = HTTP)
- `TidalState` champs : `timestamp`, `current_direction`, `current_speed`, `water_height`

### References

- `voyageur/tidal/protocol.py` — `TidalProvider` (boîte noire, ne pas modifier)
- `voyageur/tidal/impl.py` — `HarmonicTidalModel` (fallback)
- `voyageur/models.py` — `TidalState` dataclass
- `voyageur/cli/main.py` — lignes ~284 et ~499 pour les `HarmonicTidalModel()` à remplacer
- `_bmad-output/planning-artifacts/epics.md` — Story 5.1 ACs
- `_bmad-output/planning-artifacts/project-context.md` — règles de style et patterns

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucune erreur de fond. `_build_tidal_provider()` retourne `object` comme type de retour pour éviter d'importer `TidalProvider` au niveau module dans `main.py` — acceptable car l'usage est entièrement duck-typed via le Protocol.

### Completion Notes List

- Ajouté `httpx>=0.27` comme dépendance runtime dans `pyproject.toml`.
- Créé `voyageur/tidal/shom_client.py` : `ShomTidalClient` (TidalProvider) avec injection `http_client` pour testabilité, fallback `HarmonicTidalModel` sur toute exception, warning sur `sys.stderr`.
- Modifié `voyageur/cli/main.py` : `_load_voyageur_config()` + `_build_tidal_provider()` — les deux `tidal = HarmonicTidalModel()` remplacés par `tidal = _build_tidal_provider()`, imports `HarmonicTidalModel` lazys supprimés.
- Modifié `tests/test_tidal.py` : 3 nouveaux tests avec `_MockHttpClient`/`_MockHttpResponse` injectés — protocol, happy path, fallback.
- 62/62 tests passent, 0 violation ruff.

### File List

- `voyageur/tidal/shom_client.py` (créé)
- `pyproject.toml` (modifié — httpx ajouté)
- `poetry.lock` (modifié — lockfile mis à jour)
- `voyageur/cli/main.py` (modifié — `_load_voyageur_config`, `_build_tidal_provider`)
- `tests/test_tidal.py` (modifié — 3 nouveaux tests)

## Change Log

- 2026-03-31 : Story 5.1 créée — SHOM Tidal API Client
- 2026-03-31 : Story 5.1 implémentée — `ShomTidalClient`, `_build_tidal_provider`, 3 tests
