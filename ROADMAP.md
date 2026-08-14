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

## État courant (baseline vérifiée sur le zip fourni)

- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy` ✅ · `pytest --cov` ✅.
- Couverture mesurée : **56,3 %** (badge à jour) ; `fail_under = 50` dans `pyproject.toml`.
- Dette connue non bloquante : ticket mypy `scripts/schedule_backup.py` (conflit de module, cf. Lot H2) ; `agents/supervisor.py:55,150` conventions dupliquées (Lot H1).

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

### Lot F — HTTP et logs 🟡 EN COURS
- [x] F1 `services/adapters/http.py:_call_with_retry` : filet avec transport httpx factice — succès immédiat, retry puis succès, timeout, exception réseau, code non retryable, backoff borné → `tests/test_adapters_http_retry.py`, 10 tests, 4 gates vertes (pytest/ruff check/ruff format/mypy) — **à committer**
- [x] F2 Extrait `is_retryable(error)` (fonction pure) : `ReadTimeout` non retryable, `HTTPStatusError`/`RequestError` retryables, reste non retryable — politique inchangée, comportement vérifié par les 10 tests F1 + 5 tests directs sur `is_retryable` (services/adapters/http.py +20/-3) — **à committer**
- [x] F3 `services/log.py:_load_logs` : filet — fichier absent, JSON valide, JSON corrompu (récupération raw_decode, fragments non-dict ignorés, objet racine non-liste), rotation (`MAX_LOG_ENTRIES`), filtre de niveau (défaut/env/alias WARN) — `tests/test_log_characterization.py`, 17 tests, 4 gates vertes — **à committer**
- [ ] **F4** Extraire un parseur de ligne pur ; séparer lecture / rotation / filtrage

### Lot G — Verrou CI front 🔴 À FAIRE
Aucun job front dans `.github/workflows/ci.yml` aujourd'hui ; vitest configuré
mais seulement 5 fichiers de test pour 16 modules JS.
- [ ] **G1** Job `frontend` dans `ci.yml` (Node explicite, `npm ci` puis `npm test` dans `static/`), vérifié en cassant un test puis en le restaurant
- [ ] **G2** Tests `static/assets/js/modules/state.js`
- [ ] **G3** Tests `utils.js`
- [ ] **G4** Tests `status.js`
- [ ] **G5** Tests `files.js`
- [ ] **G6** Tests `settings.js`

Priorité aux fonctions pures, aux événements et aux contrats réseau simulés. Pas de tests DOM fragiles.

### Lot H — Nettoyage et cliquet de couverture 🔴 À FAIRE
- [ ] **H1** `agents/supervisor.py:55,150` : caractériser puis factoriser les conventions dupliquées
- [ ] **H2** Ticket mypy `scripts/schedule_backup.py` : trancher une stratégie (package explicite / `MYPYPATH` / déplacement vers `tools/`), sans `exclude` mécanique
- [ ] **H3** `fail_under` en cliquet montant : relevé après chaque lot vert (actuellement 50), cible **60** en fin de plan ; badge régénéré depuis la CI
- [ ] **H4** Purge finale de cette ROADMAP et de `BACKLOG.md` : chaque ligne restante pointe un commit ou une mesure réelle

## Ordre d'exécution restant

```text
F4 → G (G1 → G6) → H (H1 → H4)
```

`Lot 8 / A, B, C, D, E` sont clos.

## Definition of done (par micro-tâche)

1. Test rouge écrit et vu échouer.
2. Code minimal pour le vert.
3. Refactor sans changer les tests.
4. Les 4 gates vertes (`ruff check`, `ruff format --check`, `mypy`, `pytest --cov`).
5. Un commit conventionnel, un seul sujet.
6. Ligne de bilan dans `BACKLOG.md` avec hash et chiffres mesurés ; `fail_under` remonté si la couverture a progressé.
