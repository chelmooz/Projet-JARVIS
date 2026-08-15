# ROADMAP — Plan micro-tâches TDD JARVIS

Suivi unique du plan d'amélioration (audit 68/100 → cible 90/100). Fusion de
l'ancien `ROADMAP.md` (Lots 0-7, clos) et de `ROADMAP_LOT8.md` (Lot 8, en cours) —
un seul document désormais, `ROADMAP_LOT8.md` est supprimé.

## Règles permanentes (à relire avant chaque tâche)

1. Cycle obligatoire : **RED** (test écrit et vu échouer) → **GREEN** (code minimal) → **REFACTOR** (sans toucher aux assertions).
2. Gates avant chaque commit, dans cet ordre : `ruff check .` · `ruff format --check .` · `mypy` · `pytest --cov`.
3. Un commit conventionnel par micro-tâche, un seul sujet. Diff ≤ 200 lignes. Stop et rapport si > 60 min.
4. Aucune assertion existante modifiée ; seuls les chemins d'`import` et de `patch()` peuvent suivre un déplacement de module.
5. Aucun test qui touche le réseau, Ollama ou le disque hors `tmp_path`.
6. KISS : aucune abstraction sans un deuxième appelant réel. Aucune couche « au cas où ».
7. Quand deux implémentations de la même règle coexistent, l'une disparaît dans la même micro-tâche. Jamais de branche de compatibilité.
8. Objectif de lisibilité, pas de compteur : fonctions courtes à responsabilité unique ; redécouper seulement si la lisibilité y gagne.
9. Ne jamais recréer de code « à l'identique supposé » : retrouver la source ou déduire le contrat des usages, verrouillé par un test.
10. Après chaque lot : mettre à jour cette ROADMAP + `BACKLOG.md` avec le hash de commit et les chiffres réellement mesurés.

## État final (plan clos, 15/08/2026)

- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy` ✅ (125 src) · `pytest --cov` ✅ (373 tests, 372 passed/1 skipped).
- Couverture mesurée : **60,85 %** (badge à jour, commit `eb3f427`) ; `fail_under = 60` dans `pyproject.toml`.
- Dette antérieure soldée : ticket mypy `scripts/schedule_backup.py` (Lot H2, commit `b35017d`) ; conventions `_profile_key`/`PROFILE_KEY` dupliquées dans `agents/supervisor.py` (Lot H1, commit `b35017d`).

---

## Historique clos — Lots 0 à 7 ✅

Tout le socle est fait : outillage CI (ruff/mypy/pytest, matrice 3.12/3.13), fixtures
de test (`sandbox_root`, fakes `ChatPort`/`VectorPort`/`EmbeddingPort`), cœur métier
en TDD (`sanitize`, `file_system`, `score`, `chunker`, `vector_weighting`,
`vector_dimension`, `router`, `selector`), contrôleurs testés via
`fastapi.testclient` (health, chat, agents, files, ratelimit, rag), refactors sous
filet (vector façade, ollama_installer découpé par plateforme), dettes ciblées
soldées (retry_after, CSP, sandbox fail-closed), reproductibilité (`uv.lock`,
vendoring offline, `release.yml`), documentation (README scindé, CONTRIBUTING,
CHANGELOG fusionné, badge de couverture). Détail des micro-tâches et hashes de
commit : voir `BACKLOG.md` (sections Lot 0 → Lot 7).

---

## Lot 8 — Nettoyage structurel post-audit (en cours)

### Lot A — Débloquer le dépôt ✅ CLOS
Le package `models/` était masqué par `.gitignore` (`ImportError: cannot import
name 'Result'`). Corrigé : `.gitignore` pointe désormais les poids réels,
`models/__init__.py` + DTO committés, double nom de module `schemas` réglé,
`tests/test_import_contract.py` verrouille la régression en CI.
→ commit `8bfacf900`.

### Lot B — Documentation en phase avec git ✅ CLOS
`ROADMAP.md` corrigé (note obsolète sur `ollama_download.py`), imports
`test_ollama_installer_security.py` vérifiés, cartographie des hotspots git
versée dans `BACKLOG.md`.

### Lot C — Source unique pour le pipeline ✅ CLOS
`PipelineService` (`pipeline.py`) confirmé comme seul chemin de production ;
`execute_pipeline_step` (mort, dupliqué) supprimé après filet de
caractérisation. Décision actée dans `ADR-013-pipeline-source-unique.md`.
→ commit `40e58505e`.

### Lot D — Cœur métier avant plomberie ✅ CLOS
- [x] D1 `services/orchestrator.py` : 16 tests (routage, fallback, vision, métriques, analytics, habitudes, injection DIP)
- [x] D2 `explicit_package_bases = true` (mypy), fix `pipeline.py:232`
- [x] D3 `tests/test_toolbox.py` : 15 tests API publique
- [x] D4 `tests/test_vector_search.py` : 9 tests (FakeVector/FakeEmbedding)
- [x] D5 `services/vector.py` : extraction `_run_bounded_search` (SRP)

### Lot E — God functions des contrôleurs ✅ CLOS
- [x] E1 `tests/test_router_e1.py` : 10 tests sur `create_app()` (routes, middlewares, contenu)
- [x] E2 `create_app` → déjà découpé en `_register_middlewares` + `_register_routes` (vérifié dans `controllers/router.py`)
- [x] E3 `controllers/warmup.py:lifespan` (178 l.) : filet de caractérisation — démarrage dégradé sans Ollama, fermeture propre, échec journalisé sans lever → commit `4b506f9`
- [x] E4 `lifespan` → extrait en `_startup_sequence` / `_shutdown_sequence`, chaque étape testable seule → commit `f78d69a`
- [x] E5 `controllers/routes/jarvis.py:handle_request` (77 l.) : filet — offline, 503, 500, image invalide, SSE (88%) → commit `cf30d39`
- [x] E6 `handle_request` → parsing / appel orchestrateur / construction de réponse isolés ; codes 4xx-5xx et format JSON préservés (69+/37-) → commit `449cd12`

### Lot F — HTTP et logs ✅ CLOS
- [x] F1 `services/adapters/http.py:_call_with_retry` : filet avec transport httpx factice — succès immédiat, retry puis succès, timeout, exception réseau, code non retryable, backoff borné → commit `28b5e32`
- [x] F2 Extrait `is_retryable(error)` (fonction pure) : `ReadTimeout` non retryable, `HTTPStatusError`/`RequestError` retryables, reste non retryable — politique inchangée → commit `0e24af5`
- [x] F3 `services/log.py:_load_logs` : filet — fichier absent, JSON valide, JSON corrompu (récupération raw_decode, fragments non-dict ignorés, objet racine non-liste), rotation (`MAX_LOG_ENTRIES`), filtre de niveau (défaut/env/alias WARN) → commit `27cc503`
- [x] F4 Extrait `_recover_json_objects(content)` (parseur pur de récupération JSON) et `_rotate(logs, max_entries)` (rotation pure) hors de `_load_logs`/`log()` ; structure d'exceptions et de logs de `_load_logs` inchangée, filtre de niveau déjà isolé dans `log()` — 7 nouveaux tests directs sur les fonctions pures → commit `9f4ce08`

### Lot G — Verrou CI front ✅ CLOS
Aucun job front dans `.github/workflows/ci.yml` avant ce lot ; vitest configuré
mais seulement 5 fichiers de test pour 16 modules JS.
- [x] G1 Job `frontend` dans `ci.yml` (Node 22, `npm ci` puis `npm test` dans `static/`), vérifié localement en cassant une assertion (`npm test` échoue) puis en la restaurant (40/40 verts) → commit `435d407`
- [x] G2 Tests `static/assets/js/modules/state.js` — 4 tests (shape initiale, singleton, `resetState`) → commit `435d407`
- [x] G3 Tests `utils.js` — 19 tests (`escHtml`, `debounce`, `toast`, `renderMarkdown`, skeletons, `autoResize`, `cachedFetch`+TTL) → commit `435d407`
- [x] G4 Tests `status.js` — 12 tests (SSE via `EventSource` factice, `pollMetrics`, `updateBadges`) → commit `435d407` ; bug de locale trouvé et corrigé après coup (`toLocaleString()` dépendait de l'OS, `4,200` vs `4 200`) → commit `74ef0f3`
- [x] G5 Tests `files.js` — 20 tests (navigation dossier, historique, autorisation/révocation de chemin, erreurs réseau) → commit `435d407`
- [x] G6 Tests `settings.js` — 16 tests (thème + localStorage, bannière hors-ligne, `restoreSettings`) → commit `435d407`

Suite frontend complète : 111 tests passent (10 fichiers, dont 5 nouveaux). Fonctions pures et contrats réseau simulés priorisés, aucun test DOM fragile.

### Lot H — Nettoyage et cliquet de couverture ✅ CLOS
- [x] **H1** `agents/supervisor.py` : conventions `_profile_key`/`PROFILE_KEY` dupliquées unifiées en une propriété `profile_key` sur `BaseAgent` (défaut `None`, surchargée dans `GenericAgent`/`CyberAgent`, héritée par `VisionAgent`) ; `_agent_name()` simplifié à un seul point d'accès ; 13 tests de caractérisation créés (`tests/test_supervisor.py`, 0 % de couverture avant) → commit `b35017d`
- [x] **H2** Ticket mypy `scripts/schedule_backup.py` : stratégie tranchée = package explicite (`scripts/__init__.py`), pas de `MYPYPATH`/déplacement ni `exclude` mécanique ; fichier entièrement typé et intégré nommément au scope mypy officiel (`pyproject.toml` → `files=`) → commit `b35017d`
- [x] **H3** `fail_under` relevé 50 → **60** (cible finale du plan), couverture mesurée 60,85 % ≥ 60 % ; badge régénéré → commit `eb3f427`
- [x] **H4** Purge finale de cette ROADMAP et de `BACKLOG.md` : marqueurs « à committer » remplacés par les hashes réels, ticket mypy résolu clos, lien mort vers `ROADMAP_CONSOLE.md` (supprimé au commit `c987e6e`) retiré de `BACKLOG.md`

**Lots 0 à 8 (A → H) tous ✅.** État figé à ce stade ci-dessus (`## État final`).

---

## Lot 9 — Durcissement post-audit ✅ CLOS

- Commit initial `bd17dbb` ("Durcissement Post-Audit") committé sans mise à jour de cette ROADMAP ni de
  `BACKLOG.md` (violation règle #10) et sans respecter le gabarit "un commit, un sujet, diff ≤ 200 lignes"
  (règle #3, 52 fichiers / 1 621 insertions mêlant refactor fonctionnel et tests).
- Chiffre "339 tests" annoncé dans le message de commit initial : **infirmé** par le rejeu réel, non
  fiable tel quel au moment du commit.
- Incident isolé : `venv/Scripts/` (binaires Windows + `pyvenv.cfg` exposant un chemin absolu et un nom
  d'utilisateur système) committé par erreur → retiré du suivi git (commit `156b6c6`), `.gitignore`
  complété (`venv/`, commit `9839d01`).
- **Rejeu réel des 4 gates** (poste Windows `H:\Projet-JARVIS`, Python 3.12.10) après correction de 3
  vagues de bugs trouvés par le rejeu lui-même : `ruff check` 87→0 erreurs (1 vrai bug F821, code mort) ;
  `mypy` 6→0 erreurs (3 vrais bugs : typo `agent_graph_factory`, route `/static/{path:path}` cassée,
  appel fantôme `LogService.close()`) ; `pytest --cov` 5 failed→0 (5 routes dupliquées dans
  `controllers/routes/system.py` interceptant les vraies routes de `router.py`).
- **Résultat final vérifié** : `ruff check` ✓ · `ruff format --check` ✓ · `mypy` (126 fichiers) ✓ ·
  `pytest --cov` → **389 passed / 1 skipped / 0 failed**, couverture 60,66–60,76 %.
- Commits : `bd17dbb`, `156b6c6`, `9839d01`, `4c84fdf`, `7846db7` (fix routes dupliquées + test
  middleware), `ce7667c` (bilan BACKLOG.md).

## Lot 1 — Caractérisation pipeline_steps / adapters http ✅ CLOS

Périmètre initial (`pipeline_steps`, `adapters_http`, `log`, `warmup`, `selector`) recentré après audit de
couverture réel : `log.py` (94 %), `warmup.py` (97 %) et `selector.py` (98 %) déjà couverts par les lots
précédents (0.6, H). Seuls deux vrais trous restaient.

- [x] `services/pipeline_steps.py` : 18 % → **100 %**, 39 tests (`tests/test_pipeline_steps_characterization.py`)
  — `select_agent`, `select_model`, `retrieve_context`, `query_model`, `save_results`, `format_output` +
  helpers privés de retry (`_should_retry`, `_wait_before_retry`, `_runner_supports_model`).
- [x] `services/adapters/http.py` : 56 % → **100 %**, 53 tests au total (16 existants de retry +
  37 nouveaux dans `tests/test_adapters_http_lifecycle.py`) — `ping`/`_check_endpoint`, `_get_http`,
  `_request_client_for_call`, `cancel_request`, `close`, `_load_base_url`/`_load_timeout`/
  `_load_keep_alive`/`_keep_alive_for` (lecture config disque + cache), `_call_streaming`/
  `_extract_stream_chunk`, et les branches restantes de `_call_with_retry` (fermeture en cours de boucle,
  client `None` en cours de boucle, budget épuisé pendant l'attente).
- **Gates (vérifiées empiriquement)** : `ruff check` ✓ · `ruff format --check` ✓ · `mypy` (126 fichiers) ✓ ·
  `pytest --cov` → **466 passed / 1 skipped / 0 failed** (était 389), couverture **63,46 %** (seuil 60 %).
- Commit : `f2f084b`.

## Definition of done (par micro-tâche)

1. Test rouge écrit et vu échouer.
2. Code minimal pour le vert.
3. Refactor sans changer les tests.
4. Les 4 gates vertes (`ruff check`, `ruff format --check`, `mypy`, `pytest --cov`).
5. Un commit conventionnel, un seul sujet.
6. Ligne de bilan dans `BACKLOG.md` avec hash et chiffres mesurés ; `fail_under` remonté si la couverture a progressé.
