# BACKLOG — JARVIS Portable

Journal des micro-tâches + décisions. Mis à jour après chaque micro-tâche.

## ROADMAP active
`ROADMAP_CONSOLE.md` — Console Tab (9��ᵉ onglet) + Command Palette (Ctrl+K).

## Micro-tâches

### MT-3 — ROADMAP TDD qualité (audit 68→90)  �� 🔧 2026-08-13
- Créé `ROADMAP.md` à la racine : suivi à cocher des LOTS 0→7. Contrat TDD strict RED→GREEN→REFACTOR.
- **Lot 0 (verrou outillage) terminé & vert** : 0.1 mypy dans dev extras · 0.2 retrait exclude ruff ·
  0.3 fail_under=0 + retrait commentaire mesure fantôme · 0.4 workflow ci.yml (push/PR, 3.12/3.13) ·
  0.5 retrait badge Tests-478 · 0.6 ruff format (4 fichiers) · 0.7 mypy vert (typage SSE + vision + override rapidocr).
- Gate validée : `ruff check .` � ✓ · `ruff format --check .` � ✓ · `mypy` � ✓ (119 src) · `pytest --cov` � ✓ (4 passed, fail_under=0).
- Note : `git commit` émet un warning « could not write multi-pack-index / geometric-repack » (Permission denied
  sur .git interne) mais le commit aboutit. À investiguer (FS/lock) — non bloquant pour l'instant.
- **Lot 1 (socle de test) terminé** : 1.1 fixture `sandbox_root` + smoke test ·
  1.2 `FakeInference(ChatPort)` + fixture `inference` ·
  1.3 `FakeEmbedding(EmbeddingPort)` + `FakeVector(VectorPort)` + fixtures `embedding`/`vector`.
  Les fakes respectent les Protocol (validé par `mypy tests/conftest.py`). 5 tests au total passent.
- **Lot 2 (noyau critique TDD) terminé** : 2.1 sanitize 96 % · 2.2 file_system 87 % ·
  2.3 score 100 % · 2.4 chunker 98 % · 2.5 vector_weighting/dimension 99 %/100 % ·
  2.6 router 100 % (bug `.task` corrigé) · 2.7 selector 98 %. Cible ≥ 85 % largement atteinte.
- **Découverte majeure (Lot 2.6)** : `import services.*` résolvait une copie périmée installée dans
  `site-packages` (`C:\Users\sangoku\AppData\Local\Programs\Python\Python312\Lib\site-packages\services\router.py`),
  qui masquait mes corrections locales. Corrigé par `pythonpath = ["."]` dans `[tool.pytest.ini_options]`
  (pyproject.toml) → pytest importe désormais le source local. �� ⚠��️ À retenir : la copie site-packages est
  un snapshot obsolète du projet ; privilégier `pip install -e .` pour que le source local soit autoritatif.
- **Lot 3.1 (API santé) terminé** : `tests/test_api_health.py` (4 tests) — `/api/status` → 200
  dégradé offline + reflète le DI injecté ; `/api/health` → 503 dégradé / 200 sain.
  Injection de fakes via `app.state.context` (DI respecté). Gates : ruff � ✓ · format � ✓ ·
  mypy 119 src � ✓ · pytest 124 passés / 1 skip � ✓.
- **Correctif config** : `pyproject.toml` `[tool.mypy]` `exclude = ["build","node_modules","\\.venv","dist"]`
  (artefacts générés, jamais source). `scripts/` RETIRÉ de l'exclude → voir ticket ci-dessous.
  Le gate qualité reste `mypy` (sans chemin, `files` = 119 src) ; `mypy .` scanne tout et révèle les dettes.
- **Hygiène 1 (site-packages) terminée** : copie périmée `jarvis-portable 5.10` désinstallée de
  `site-packages` ; réinstallée en éditable (`pip install -e .[dev]` → `jarvis-portable 6.0` → `H:\Projet-JARVIS`).
  Vérifié : `import services/controllers/agents` depuis un autre dossier résout vers le dépôt.
  `pythonpath=["."]` dans pyproject reste en filet de sécurité (inoffensif).
- **Hygiène 2 (.gitignore) terminée** : `dist/` ajouté (build/ déjà présent). `scripts/` retiré de l'exclude mypy
  (ne pas masquer la dette — ticket ouvert).
- **Lot 3.2 (API chat/routage) terminé** : `tests/test_api_chat.py` (7 tests) — POST `/api/jarvis`
  route via `AgentRouter` réel injecté dans un orchestrateur factice (DI) : préfixe @
  (cyber/dev/network), mots-clés (network), fallback `dev` + nominal via `FakeInference`
  (200), payload invalide (422), body trop gros (413 via patch `MAX_BODY_SIZE`).
  Gates : ruff � ✓ · format � ✓ · mypy 119 src � ✓ · pytest 131 passés / 1 skip � ✓ · couv 47.8 % ≥ 46 %.
- **Lot 0 (reconcilié) + Hygiène terminés** : 0.4 ci.yml conforme · 0.5 badge Tests-478 absent ·
  0.6 exclude ruff absent · 0.7 `fail_under=46` (mesuré 48−2) · Hygiène1 site-packages
  désinstallé + install éditable · Hygiène2 `.gitignore` dist/ + ticket mypy scripts/ ·
  Hygiène3 `git fsck` OK (dangling seuls).
- **Lot 3.3 (API agents) terminé** : `tests/test_api_agents.py` (5 tests) — `GET /api/agents` 200
  (structure), `POST /api/agents/assign` 200 (assigne, fichiers isolés via tmp+monkeypatch),
  404 profil inconnu, 400 modèle invalide, 500 fichier profils absent. Gates : ruff � ✓ · format � ✓ ·
  mypy 119 src � ✓ · pytest 136 passés / 1 skip � ✓ · couv 48 % ≥ 46 %.
- **Lot 3.4 (API fichiers) terminé** : `tests/test_api_files.py` (4 tests) — list 200 dans le
  sandbox (config d'auth isolée en tmp), refus dossier non autorisé (fail-closed) et hors sandbox
  (`error_type=not_authorized`), lecture fichier inexistant (`Pas un fichier`). Gates : ruff � ✓ ·
  format � ✓ · mypy 119 src � ✓ · pytest 140 passés / 1 skip � ✓ · couv 48 % ≥ 46 %.
- **Lot 3.5 (API rate limit) terminé** : `tests/test_api_ratelimit.py` (2 tests) — sous quota 200 +
  en-têtes `X-RateLimit-Limit`/`Remaining` ; au-delà 429 + `retry_after` cohérent avec
  `Retry-After` (patch `MAX_REQUESTS=2` + reset état). Gates : ruff � ✓ · format � ✓ · mypy 119 src � ✓ ·
  pytest 142 passés / 1 skip � ✓ · couv 49 % ≥ 46 %.
- **Lot 3.6 (API RAG/recherche) terminé** : `tests/test_api_rag.py` (3 tests) — `GET /api/search`
  avec `FakeVector` injecté : 200 + résultats/pagination (total/count/limit/offset), 400 query vide,
  texte scrubbé préservé. Gates : ruff � ✓ · format � ✓ · mypy 119 src � ✓ · pytest 145 passés / 1 skip � ✓ ·
  couv 49 % ≥ 46 %.
- **LOT 3 COMPLET** (API & intégration, 3.1→3.6) : 17 nouveaux tests d'API, tous verts, DI via
  `app.state.context` respectée partout. Prochaine phase : **Lot 4 (refactors sous filet)**.
- **Lot 4.1 (vector.py façade) TERMINÉ** : `services/vector.py` délègue déjà ses opérations feuilles aux sous-modules
  (`vector_index`, `search`, `cache`, `stats`, `docs`, `embedder`) et ne conserve que l'orchestration.
  C'est l'état final souhaité. Déplacer l'orchestration dans `vector_search.py` ne ferait que renommer le problème
  en ajoutant des paramètres d'injection (embed, get_matrix, cache, now_fn) : violation de KISS, pas de gain.
  � ✅ 2026-08-13

### Ticket ouvert — mypy : conflit de module `scripts/schedule_backup.py`
- **Symptôme** (sur `mypy .`) : `scripts/schedule_backup.py: error: Source file found twice under
  different module names: "schedule_backup" and "scripts.schedule_backup"`.
- **Cause** : la racine du dépôt est sur `sys.path` (install éditable `.pth`), donc `schedule_backup.py`
  est importable à la fois comme module top-level `schedule_backup` et comme `scripts.schedule_backup`
  (namespace package). mypy refuse la double définition.
- **Impact** : n'affecte PAS le gate `mypy` (sans chemin, `files` = 119 src). Apparaît uniquement sur `mypy .`.
- **Résolutions possibles** (à choisir en Lot ultérieur) :
  1. `mypy --explicit-package-bases` + `MYPYPATH`/section `[tool.mypy]` `explicit_package_bases = true`
     pour forcer le mapping `scripts.*` ;
  2. ou ajouter `scripts/__init__.py` (rend `scripts` package explicite) — vérifier qu'aucun import
     `from schedule_backup import ...` ne casse ;
  3. ou déplacer `scripts/` hors de la racine scannée par mypy (ex. `tools/`).
- **Décision** : NE PAS exclure `scripts` de mypy (masquerait la dette). Traiter en nettoyage dédié.

### MT-1 — Backend champ `source` sur JarvisRequest  � ✅ 2026-08-13
- `models/schemas.py` : `source: Literal["chat","console","palette"] = "chat"` (default non-breaking).
- `services/analytics.py` + `ports/__init__.py` : `track_query(..., source="chat")` kwarg non-breaking.
- `controllers/routes/jarvis.py` : lit `body.source`, propage aux 2 `_track_query` (JSON + SSE).
- Vérif (pré-déploiement, pas de serveur) : `JarvisRequest(task='hello').source == 'chat'`,
  explicite 'console' OK, import `controllers.routes.jarvis` OK. Comportement inchangé sans `source`.

### MT-1.5 — DRY `routing_prefixes` sur GET /api/agents  � ✅ 2026-08-13
- `controllers/routes/agents.py` : réutilise `services/router.load_routing_config()` (pas de re-lecture YAML).
- `ROUTING_PREFIXES = list(...prefix_map.keys())` exposé dans la réponse `ok()` (champ en plus, non-breaking).
- Vérif : `ROUTING_PREFIXES == ['@cyber','@dev','@network','@hardware','@vision','@orchestrateur','@techlead','@devops','@designer','@datasecu']`.

### MT-2 — console-client.js (module pur, zéro DOM)  � ✅ 2026-08-13
- `static/assets/js/modules/console-client.js` : `parseCommand` (regex + erreur explicite), `sendCommand`
  (POST /api/jarvis, AbortController 30 s, normalise 5xx/réseau/timeout en {ok,data,error}, jamais throw),
  `fetchAgents`/`agentsFromApi` (depuis /api/agents via cachedFetch), `consoleStore` singleton (handoff).
- Tests focused : `test/console-client.test.js` (16 tests, vitest/jsdom). `npm install` fait (réseau OK).
- Résultat : 16/16 pass.

### MT-3 — command-palette.js (overlay Ctrl+K)  � ✅ 2026-08-13
- `static/assets/js/modules/command-palette.js` : classe `CommandPalette` (mount/open/close/toggle,
  autocomplétion filtrée sur `routing_prefixes` via `fetchAgents`, submit avec `source:'palette'`,
  Escape, bouton « Ouvrir en Console » → `handoff()` dispatch `jarvis:palette-handoff` + `consoleStore`).
- Tests focused : `test/command-palette.test.js` (9 tests). Résultat : 9/9 pass.

### MT-4 — console-tab.js + index.html (9��ᵉ onglet)  � ✅ 2026-08-13
- `static/index.html` : 9��ᵉ `<button class="tab-btn" data-tab="console">`, `<div id="tab-console">`
  (scrollback + input + badge connexion), `<link>` console.css.
- `static/assets/js/modules/console-tab.js` : classe `ConsoleTab` (scrollback append-only, badge agent,
  historique localStorage `jarvis_console_history` ≤50, nav ↑/��↓, `jarvis:status-updated` → badge connexion,
  `_onHandoff` bascule onglet + pré-remplit + (re)exécute).
- `static/assets/css/console.css` : styles Console + Palette (tokens existants réutilisés).
- `app.js` : focus `#console-input` à l'ouverture de l'onglet (additif).
- Tests focused : `test/console-tab.test.js` (7 tests). Résultat : 7/7 pass.

### MT-5 — Handoff Palette → Console  � ✅ 2026-08-13
- `command-palette.js` (bouton « Ouvrir en Console » + `handoff()`) dispatch `jarvis:palette-handoff`
  + `consoleStore.setLast`. `console-tab.js` `_onHandoff` bascule onglet + pré-remplit + (re)exécute.
- Zéro nouvelle route, zéro dépendance. Couvert par les tests MT-3/MT-4.

### MT-6 — status.js (event)  � ✅ 2026-08-13
- `static/assets/js/modules/status.js` : fin d'`onmessage` de `connectStatusSSE()` →
  `document.dispatchEvent(new CustomEvent('jarvis:status-updated', { detail: s }))`.

### MT-7 — boot.js (wiring)  � ✅ 2026-08-13
- `static/assets/js/modules/boot.js` : `consoleTab.mount()`, `palette.mount()`, listener unique
  `keydown` Ctrl/��⌘+K on `document` → `palette.toggle()`. Expose `window.__jarvisPalette/Console`.

### MT-8 — Documentation  � ✅ 2026-08-13
- `README.md` est l'index des ADR (pas un doc features) → section « Console Tab + Command Palette »
  ajoutée dans `CHANGELOG.md` (niveau détail onglet Outils) + guide pas-à-pas.

### MT-9 — Finalisation  � ✅ 2026-08-13
- `npx vitest run` (static) : **40/40** pass (console-client 16, command-palette 9, console-tab 7, + legacy).
- Python : imports OK (schemas, analytics, routes agents/jarvis, ports) ; `JarvisRequest.source` défaut 'chat'.
- `ruff check` sur les fichiers Python touchés : **All checks passed!**.
- `.gitignore` : ajout `node_modules/`, `.pytest-temp/` (artifacts de test exclus du suivi).
- Aucun commit (conforme AGENTS.md). `git status` montre les nouveaux fichiers Console attendus + modifs
  préexistantes (agents/vision.py, services/selector.py, README.md, AGENTS.md, docs/adr/ADR-010…)
  issues d'une session antérieure, hors périmètre de cette exécution.

## Fichiers livrés (Console/Palette)
- `static/assets/js/modules/console-client.js` (+ test)
- `static/assets/js/modules/command-palette.js` (+ test)
- `static/assets/js/modules/console-tab.js` (+ test)
- `static/assets/css/console.css`
- Édits : `index.html`, `app.js`, `boot.js`, `status.js`
- Backend : `models/schemas.py`, `services/analytics.py`, `ports/__init__.py`, `controllers/routes/agents.py`, `controllers/routes/jarvis.py`
- Doc : `CHANGELOG.md`

## Garde-fous
- Aucun commit sans accord explicite.
- TDD-lite (tests focused sur logique pure).
- Refactor > patch ; additif ; zéro nouvelle route/dépendance.

## Revue & révision complète (2026-08-13, post-livraison Console v6.0)

### Revue (clean-code)
- `ruff check .` : 19 erreurs (imports morts, whitespace, trailing newline, I001, UP035, SIM105).
  → **18 auto-fixées** (`ruff check --fix .`).
- Incohérence DRY : `parseCommand` (`@agent tâche`) dupliqué dans `command-palette.js`
  (`_agentFromInput`/`_taskFromInput`) et `console-tab.js` (`_onHandoff`).

### Révision (refactor > patch)
- `controllers/warmup.py` : `try/except/pass` → `contextlib.suppress(Exception)` (SIM105).
- `command-palette.js` : supprime `_agentFromInput`/`_taskFromInput`, réutilise `parseCommand`
  (validation explicite, erreur affichée). `parseCommand` importé depuis `console-client.js`.
- `console-tab.js` : `_onHandoff` utilise `detail.agent`/`detail.task` (plus de duplication).
- `console-client.js` : retire l'export mort `__test__`.
- Résultat : `ruff check .` → **All checks passed!** ; `npx vitest run` → **40/40 pass** ;
  imports backend OK.

### README
- Section Tests enrichie : ajout vitest frontend (40 tests) + note `ruff check .` à 0 erreur.
- État global : v6.0, 9 onglets + Palette Ctrl/��⌘+K.

### Connaisseances non traitées (gaps signalés, hors périmètre de cette passe)
- `GET /api/agents` : `agentsFromApi` renvoie `model: null` pour les clés de routage
  (`cyber/dev/network/hardware/vision`) car `agent_model_map` est indexé par profil
  (orchestrateur/techlead/…). Mismatch documenté dans ROADMAP_CONSOLE.md MT-0 ; à réconcilier
  côté backend (ex. liste `agents` résolue) si besoin.
- Revue architecture large (SOLID/skill `solid`) non faite : la base est saine, passage
  lint/tests verts ; refactoring profond non lancé pour éviter tout risque sur la base stable.
- T4.2 test(execute_pipeline_step) écrit en TDD : 3 tests dans tests/test_pipeline_steps.py — valides agent_runner, inference, retry. Refactor pipeline.py pour déléguer à pipeline_steps.py en suivi."
- T1 terminé (2026-08-14) : 2 commits atomiques (`docs(roadmap)` + `fix(ollama)`), 4 gates vertes (ruff/check/mypy/pytest --cov), `fail_under=46` avec mesure réelle 49,41 %. ROADMAP.md mise à jour (Lots 1–3 cochés, Lot 4.1 vector façade, règle 4 amendée inscrite). `_install_linux_apt` duplication corrigée (1 seule occurrence).

### Tickets TODO → BACKLOG (Lot 5.5, 2026-08-14)
Les TODO restants sont basculés ici (plus dans le code) — voir ROADMAP Lot 5.5 :
- **supervisor.py:57** `TODO(refacto-SOLID)` : ajout propriété publique `name` sur `BaseAgent` — supprimer le getattr multi-conventions (`_profile_key`/`PROFILE_KEY`) dans `_agent_display_name`.
- **supervisor.py:153** `TODO(refacto-SOLID)` : modéliser un union type `RunOutcome = AgentRunResult | TimeoutResult` au lieu du champ de contrôle `timeout` ajouté au dict nominal.
- **di.py:107** `TODO` : `agent_runner=None` passé à `PipelineService` — décider du câblage (cf. tickets pipeline_steps agent_runner).

### LOT 5 — Dettes ciblées livrées (2026-08-14)
- **5.1** (`fix(middlewares)`) : `retry_after` dérivé de `services.ratelimit.WINDOW` (source unique de vérité) — test `test_429_retry_after_derived_from_ratelimit_window` (RED→GREEN).
- **5.2** (`refactor(middlewares)`) : `_setup_middlewares` → `setup_middlewares` (public), import `context.py` mis à jour — test `tests/test_middlewares_public_api.py` (RED→GREEN).
- **5.3** (`test(middlewares)`) : CSP nonce-based **sans** `unsafe-inline`, JS déjà externalisé en modules — verrou de régression `tests/test_csp_policy.py` ; docstring `middlewares.py` corrigé (dette devenue fausse).
- **5.4** (`docs(env)`) : commentaire `.env.example:37` corrigé (fail-closed), `ADR-011-sandbox-fail-closed.md` créé.
- **5.5** : 3 TODO basculés en tickets ci-dessus.
- **5.6** : références aux tests fantômes nettoyées (`context.py`, `file_system.py`).
- Gates (post-5.6) : `ruff check .` ✓ · `ruff format --check .` ✓ · `mypy` ✓ (120 src) · `pytest --cov` ✓ (178 pass / 1 skip, 50,15 % ≥ 46 %) · `fail_under` inchangé (palier suivant 47 selon ROADMAP).

### MT-4 — Lot 4.3 analysis_audit reventilation (finalisée)  � ✅ 2026-08-14
- La reventilation était **architecturalement déjà en place** à la base : `QualityAuditor` (services/analysis_audit.py) agrège via `Analyzer` (services/analysis.py), qui dispatche vers les feuilles `analysis_security/performance/maintainability/standards/core`. Commit `e89f3826` avait ajouté les imports directs `analysis_core` (`_PROJECT_ROOT`, `_SOURCE_DIRS`, `_TEST_DIR`, `_WEIGHTS`, `_count_lines`, `_py_files`) + noqa E402.
- Restait : `ruff format` de `analysis_audit.py` (1 blank line, commit `c5bca40d`). Gates vertes : ruff ✓ · format ✓ · mypy ✓ (121 src) · pytest ✓ (178/1, cov 50,26 % ≥ 46 %). ROADMAP : Lot 4.3 coché.

### MT-5 — T4 extraction archives (Lot 4.4b)  � ✅ 2026-08-14
- `services/ollama_archive.py` créé (65 l.) : `_extract_tar_zst` + `_safe_extract_zip` coupés-collés à l'identique depuis `ollama_installer.py`. Imports réels : os, subprocess, zipfile, stat, logging, Callable, `LAUNCHER_WAIT_TIMEOUT` (config.constants). `_LogFn` dupliqué (convention du dépôt : alias par module, cf. ollama_download.py).
- `ollama_installer.py` : imports morts `zipfile`/`stat` retirés ; ré-export `from services.ollama_archive import _extract_tar_zst, _safe_extract_zip` ajouté à `__all__` (ruff voit le ré-export volontaire, tests inchangés). Aucun doublon de `def` (vérifié). Commit `e677d10e`.

### MT-6 — Lot 6 Reproductibilité  � ✅ 2026-08-14
- **6.1** `uv.lock` (TOML, 59 packages épinglés) commit `4dcbd6465` + `requirements.lock` (export plat `uv export --no-emit-project`) pour pip.
- **6.2** uv 0.12.3 a RETIRÉ `uv pip download` → repli `pip download` (args identiques). Contrainte pip 26+ : `--platform` exige `--only-binary=:all:` (ou `--no-deps`) ; `requirements.lock` étant plat, `--no-deps` suffit. Exception : `antlr4-python3-runtime==4.9.3` (transitif de `omegaconf==2.3.1`, épinglé `==4.9.*`, via rapidocr) n'a AUCUNE wheel → sdist pur Python téléchargé une fois (setuptools présent dans le Python portable). `scripts/vendor_wheels.py` commité `8c4987bcb` ; `vendor_wheels/` ajouté à `.gitignore`.
- **6.3** `scripts/install.py` : `_vendor_find_links()` détecte `vendor_wheels/[/plateforme]` → `pip install --no-index --find-links` (mode offline). Commit `2d8574370`.
- **6.4** `docs/adr/ADR-012-distribution-offline.md` + section Reproductibilité dans `docs/DEVELOP.md` (Prérequis corrigé : `pip install .` au lieu de `requirements.txt` obsolète). Commit `5cce77dd1`.
- **6.5** `verify_release.py` : `version_sources()` = pyproject.toml + `config/constants.py` (regex `VERSION: Final[str]`) + `bin/VERSION.json` + launchers `JARVIS.bat/.sh` → `check_version_coherence()`. Workflow `.github/workflows/release.yml` (push tag `v*`) : `verify_release.py` + cohérence tag↔sources. Les 4 sources annoncent 6.0. Commit `f57ec6c85`.
- **6.6** smoke test ALREADY couvert (Lot 3.1) : `tests/test_api_health.py::test_status_200_offline_degraded` (GET `/api/status` → 200 sans Ollama, enveloppe `{data, error:null}`). Note ROADMAP : la route réelle est `/api/status` (`router.py:239`), pas `/api/system/status`.
- Gates Lot 6 : ruff ✓ · format ✓ · pytest 178/1 ✓ · cov ≥ 46 % ✓.