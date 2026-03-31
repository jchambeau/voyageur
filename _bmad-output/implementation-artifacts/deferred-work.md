# Deferred Work

## Deferred from: code review of 1-1-project-scaffold-setup (2026-03-29)

- CLI input validation for `--step` (no bounds check on valid values 1/5/15/30/60) — belongs in Story 2.4 CLI command implementation
- CLI input validation for `--from`/`--to`/`--wind`/`--depart` (no format/range checking) — belongs in Story 2.4 CLI command implementation
- Hard dependency on system PROJ/GEOS libraries not documented in README — add install prerequisites section when project nears first real use
- No CI/CD pipeline configured — out of scope for MVP scaffold; address when repo is pushed to remote

## Deferred from: code review of 1-2-shared-data-models (2026-03-29)

- Datetime fields accept naive datetimes (no `__post_init__` guard) — validation UTC appartient à la frontière CLI (Story 2.4)
- `BoatProfile.default_step` accepte n'importe quel entier (valeurs valides: 1,5,15,30,60) — validation = Story 3.3
- `BoatProfile` numeric fields (loa, draft, sail_area) acceptent valeurs négatives/NaN/zero — validation = Story 3.3
- Heading/direction fields acceptent valeurs hors [0, 360) — normalisation = module routing (Story 2.2)
- `Route.waypoints` liste muable extérieurement (pas de copy-on-assign) — concern architectural routing module
- NaN/Inf acceptés silencieusement dans speed fields (speed_over_ground, current_speed, speed) — validation = frontière tidal/routing
- `Route.total_duration` accepte timedelta négatif — routing module assure cohérence à la construction
- `water_height` accepte valeurs négatives (ambiguïté sous datum) — Story 2.1 tidal module
- Cohérence interne de Route non enforced (departure_time/waypoints/total_duration) — routing module construit la cohérence
- Pas de politique epsilon pour comparaisons float sécurité-critiques (ex: water_height > draft) — Story 3.2 safety evaluation
- `BoatProfile` non frozen (champs muables post-construction) — incompatible avec `voyageur config update` (Story 3.3)

## Deferred from: code review of 1-3-module-interface-protocols (2026-03-29)

- `@runtime_checkable` vérifie seulement l'existence du nom de méthode, pas la signature (arity/types) — limitation Python; détection complète des signatures = mypy/pyright, à considérer lors de l'ajout d'un linter statique
- Datetime naive accepté au niveau Protocol sans guard `__post_init__` — carryover Story 1.2, validation = frontière CLI (Story 2.4)
- `intersects_land` avec route vide (`[]`) non testée — comportement à définir dans Story 3.1 (implémentation CartographyProvider)
- Risque d'évolution Protocol (ajout d'une méthode casse silencieusement les implémenteurs existants) — concern architectural, à adresser si un registre de providers est introduit
- Chemin `True` de `intersects_land` (route qui croise la terre) non couvert par les tests Protocol — tests de comportement à ajouter dans Stories 2.2 et 3.1

## Deferred from: code review of 2-1-harmonic-tidal-model (2026-03-29)

- Datetime naïf passé à `get_current` lève `TypeError` (soustraction aware/naïve) — validation = frontière CLI (Story 2.4); carryover Stories 1.2/1.3
- `data/ports.yaml` potentiellement absent d'un wheel distribué (aucun `[tool.poetry] include` pour les fichiers non-Python) — emballage complet = Story 5.x ou lors de la première distribution
- Aucune validation des bornes géographiques (position mondiale acceptée, IDW extrapole hors zone normande) — hors AC MVP; à considérer si extension géographique (Story 4.x)
- Absence de validation de schéma YAML (`KeyError` sur clé manquante dans ports.yaml) — `ports.yaml` embarqué sous contrôle développeur; schema validation = sur-ingénierie pour MVP
- `speed >= 0.0` pour flood vs spec `speed > 0` — comportement à vitesse exactement nulle (étale) non spécifié; sans impact fonctionnel
- Tests fragiles si fixture `now` tombe sur un étale (speed = 0, direction indéfinie) — fixture fixe `2026-03-29 08:00 UTC` stable pour MVP; à re-vérifier si fixtures changent
- ~~ruff exclut `pytest.py` inexistant~~ — **FIXED** (nettoyage post-MVP, les deux exclusions `main.py` et `pytest.py` supprimées)

## Deferred from: code review of 2-2-direct-route-propagation-algorithm (2026-03-29)

- 2000 waypoints identiques quand SOG=0 (vent debout + courant nul) — comportement voulu per AC4 (MAX_STEPS = limite de sécurité spécifiée) ; le test `test_zero_wind_zero_current_does_not_raise` valide que ça ne lève pas d'exception
- Pas de signal de complétion pour distinguer route tronquée (MAX_STEPS) de route arrivée — changement de modèle `Route` (ajout d'un champ `reached_destination`) hors scope story 2.2 ; à considérer dans la couche output/CLI
- `step_minutes=0` ou négatif accepté silencieusement (`step_sec=0` → distance nulle, temps figé) — validation = frontière CLI Story 2.4 (déjà dans deferred-work)
- Waypoint d'arrivée final enregistre `heading` et `sog` de l'étape précédente (position avant avancement) — cosmétique pour MVP, impact négligeable sur la lisibilité de la timeline
- `test_waypoint_timestamps_increment` vérifie `waypoints[:-1]` uniquement — le timestamp du waypoint d'arrivée n'est pas validé ; gap mineur de couverture AC2
- Datetime naïf accepté en `departure_time` sans exception — pre-existing, validation = frontière CLI Story 2.4
- `wind.speed` ou `current_speed` négatif non rejeté (inversion silencieuse du vecteur) — pre-existing, validation = frontière CLI/tidal
- `CartographyProvider.intersects_land()` non appelé dans la boucle de propagation — intentionnel MVP ; Story 3.1 implémente la détection d'obstacle

## Deferred from: code review of 2-3-ascii-80-column-output-formatter (2026-03-29)

- ~~`_fmt_duration` utilise `int(td.total_seconds() / 60)`~~ — **FIXED** (`int(td.total_seconds()) // 60`)
- ~~`_fmt_dir_spd` produit 7 chars (au lieu de 8) pour speed < 10 kn~~ — **FIXED** (`f"{speed:4.1f}"` → `" 90/ 5.0"` = 8 chars)
- `_fmt_sog` overflow théorique pour SOG ≥ 100 kn : `f"{sog:4.1f}kn"` → `"100.0kn"` = 7 chars — impossible en voilier (SOG réaliste < 20 kn) ; à corriger si extension à des embarcations rapides
- ~~`_elapsed` colonne TIME déborde à 6 chars pour routes > 99h~~ — **FIXED** (`h < 100` garde `{h:02d}`, sinon `{h}` sans padding)

## Deferred from: code review of 2-4-cli-route-planning-command (2026-03-29)

- ~~`--step` non validé contre l'ensemble autorisé {1,5,15,30,60}~~ — **FIXED** (validation explicite `if step not in (1,5,15,30,60)` + Exit(1))
- ~~`_parse_wind` direction non bornée à [0, 360)~~ — **FIXED** (`direction >= 360.0` → return None → erreur utilisateur)
- `_parse_position` coordonnées hors limites WGS84 acceptées ("91N/180E") — hors scope spec MVP, pyproj gère les dépassements en WGS84 sans crash ; à corriger si validation stricte des entrées géographiques requise
- Tests CLI manquants : lat/lon input, --step invalide, boat.yaml absent/malformé — spec Story 2.4 demande 2 tests minimaux (satisfaits) ; couverture complète déférée à Story QA ultérieure

## Deferred from: code review of 3-1-coastal-obstacle-detection (2026-03-29)

- Faux positif shapely `intersects` au contact de frontière [impl.py:35] — `intersects` retourne True si la ligne touche seulement la frontière (sans la traverser) ; `crosses` éviterait ça mais exclurait les cas légitimes de contact ; limitation inhérente au prédicat, acceptable pour MVP
- Faux négatif si waypoint entièrement à l'intérieur d'un polygone [impl.py:32] — si deux waypoints consécutifs sont tous les deux dans un polygone sans que le segment en croise la frontière, pas de détection ; correction = ajouter `polygon.contains(Point(lon, lat))` par waypoint ; hors scope MVP
- Pas de polygones de hauts-fonds distincts dans normandy.geojson — spec dev notes reconnaît que les données sont simplifiées pour MVP (deux polygones côtiers approximatifs) ; données OSM précises avec hauts-fonds prévues en Story 4+

## Deferred from: code review of 3-2-safety-threshold-evaluation (2026-03-30)

- Vent global non par-waypoint [routing/planner.py] — design MVP documenté dans docstring planner ("constant wind conditions for the passage (MVP)") et dans les tasks de la story ; correction = ajouter wind_speed par waypoint, scope Story 4+
- `max_dist_shelter` absent du fallback boat.yaml [cli/main.py] — shelter non implémenté MVP ; à implémenter avec les données abri dans Story 4+
- `max_dist_shelter` non transmis à `SafetyThresholds` [cli/main.py] — même raison ; le champ existe dans le dataclass mais `evaluate_route` ne le vérifie pas
- 80 colonnes dépassées par marqueur ⚠ [output/formatter.py] — esthétique ; le row atteint ~60 chars (simple-width) ou ~62 (double-width terminal) ; contrainte fonctionnelle non impactée
- Pas d'alerte stderr pour flags partiels [cli/main.py] — UX : si N < total waypoints sont flagués, aucun message explicite n'est émis au-delà du ⚠ inline et du footer "Flags: N" ; amélioration UX hors scope
- Mutation `evaluate_route` sans option immutable [routing/safety.py] — documenté dans docstring ; unique appelant en CLI ; mode copy-on-eval = amélioration future si evaluate_route est réutilisé en dehors du CLI
- Route origin=dest flaguée → Exit(1) quand 1 waypoint + threshold dépassé — correct per AC4 ; comportement surprenant mais spec-correct

## Deferred from: code review of 5-1-shom-tidal-api-client (2026-03-31)

- `httpx.Client` jamais fermé dans `ShomTidalClient.__init__` [shom_client.py:23] — CLI process court ; `ResourceWarning` théorique ; gestion explicite (.close() ou context manager) = Story 5.x
- Datetime naïf passé à `at.isoformat()` sans timezone [shom_client.py:36] — pre-existing ; validation UTC = frontière CLI (Story 2.4, déjà déféré)
- API key présente dans les params dict httpx — visible dans les tracebacks d'exception [shom_client.py:36] — risque sécurité faible, hors scope MVP ; httpx ne sérialise pas les params dans les exceptions par défaut
- `capsys: object` type hint avec `# type: ignore[attr-defined]` [tests/test_tidal.py:129] — fonctionne correctement ; amélioration style = `pytest.CaptureFixture[str]` si mypy ajouté
- `http_client: httpx.Client | None` annotation trop stricte pour l'injection de mocks [shom_client.py:20] — fonctionne à runtime (duck-typing) ; correction = Protocol ou `Any` si type-checking strict requis

## Deferred from: code review of 4-3 + 4-4 (2026-03-31)

- ~~`DepartureResult.time_saved` peut être négatif~~ — **FIXED** (`max(..., timedelta(0))` dans `departure.py`)
- ~~`baseline_departure` non validée contre `window_start`/`window_end` dans `OptimalDeparturePlanner.scan`~~ — **FIXED** (`warnings.warn(UserWarning)` si `baseline ∈ [window_start, window_end]`)
- ~~Fenêtre plus courte que `scan_interval_minutes` sans avertissement~~ — **FIXED** (warning `⚠ --window shorter than 30-minute scan interval` dans `cli/main.py`)

## Deferred from: code review of 3-3-boat-profile-management (2026-03-30)

- `min=0.0` accepte loa/draft/sail_area=0 [cli/config.py] — pre-existing : _load_boat accepte aussi ces valeurs depuis YAML ; validation métier (loa > 0) hors scope MVP
- YAML corrompu → _load_existing retourne {} → merge silencieux avec défauts codés en dur [cli/config.py] — comportement intentionnel pour mises à jour partielles ; avertissement utilisateur = amélioration UX future
- ~~`_build_profile` dead code avec KeyError non gardé [cli/config.py]~~ — **FIXED** (supprimé, import `BoatProfile` retiré)
- ~~`ctx.invoked_subcommand` guard unreachable [cli/config.py]~~ — **FIXED** (supprimé, paramètre `ctx` retiré)
- Race TOCTOU entre exists() et read_text() dans --show [cli/config.py] — pattern identique dans _load_boat ; scénario pathologique, hors scope MVP
