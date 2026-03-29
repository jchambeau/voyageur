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
- ruff exclut `pytest.py` inexistant — héritage Story 1.1, à nettoyer lors d'un refactor pyproject.toml

## Deferred from: code review of 2-2-direct-route-propagation-algorithm (2026-03-29)

- 2000 waypoints identiques quand SOG=0 (vent debout + courant nul) — comportement voulu per AC4 (MAX_STEPS = limite de sécurité spécifiée) ; le test `test_zero_wind_zero_current_does_not_raise` valide que ça ne lève pas d'exception
- Pas de signal de complétion pour distinguer route tronquée (MAX_STEPS) de route arrivée — changement de modèle `Route` (ajout d'un champ `reached_destination`) hors scope story 2.2 ; à considérer dans la couche output/CLI
- `step_minutes=0` ou négatif accepté silencieusement (`step_sec=0` → distance nulle, temps figé) — validation = frontière CLI Story 2.4 (déjà dans deferred-work)
- Waypoint d'arrivée final enregistre `heading` et `sog` de l'étape précédente (position avant avancement) — cosmétique pour MVP, impact négligeable sur la lisibilité de la timeline
- `test_waypoint_timestamps_increment` vérifie `waypoints[:-1]` uniquement — le timestamp du waypoint d'arrivée n'est pas validé ; gap mineur de couverture AC2
- Datetime naïf accepté en `departure_time` sans exception — pre-existing, validation = frontière CLI Story 2.4
- `wind.speed` ou `current_speed` négatif non rejeté (inversion silencieuse du vecteur) — pre-existing, validation = frontière CLI/tidal
- `CartographyProvider.intersects_land()` non appelé dans la boucle de propagation — intentionnel MVP ; Story 3.1 implémente la détection d'obstacle
