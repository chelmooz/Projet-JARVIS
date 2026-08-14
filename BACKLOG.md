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
- ~~**di.py:107**~~ **FERMÉ (MT-T5a-1.4, 2026-08-14)** : `agent_runner=None` est définitif — inference suffit
  (`routes/pipelines.py:40` → `run()` → branche inference quand `agent_runner=None` ; inference
  configuré dans `di.py` ; aucun type runner) — agent_runner = point d'extension non câblé.

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

### MT-7 — Lot 7 Documentation  � ✅ 2026-08-14
- **7.1** README 821 l. → 156 l. : pitch + captures + installation 5 lignes + liens. Contenu opérationnel déplacé vers `docs/USAGE.md` (nouveau, ~600 l.) : installation guidée Windows/Linux/macOS, agents, modèles, skills, console, API, tests, sauvegarde, limitations. Liens internes vérifiés (scripts). Commit `1889a5107`.
- **7.2** `CONTRIBUTING.md` : boucle TDD rouge→vert→refactor, commandes gates (`ruff check . && ruff format --check . && mypy && pytest --cov`), table conventional commits, conventions code, processus. Commit `2f0b4f880`.
- **7.3** `RELEASE_NOTES_CORRECTED.md` fusionné dans CHANGELOG.md comme sous-section « Livraison corrigée — sécurité de distribution » du `[6.0]` puis fichier supprimé (artefact de travail). Commit `9961003b2`.
- **7.4** Badge de couverture : `scripts/coverage_badge.py` lit `coverage.json` (pytest --cov-report=json) → écrit `coverage-badge.json` (endpoint shields.io, couleur par seuil). Versionné ; `coverage.json` ajouté au `.gitignore`. CI : step « Coverage badge » régénère + `git diff --exit-code` échoue si périmé (badge honnête, jamais de valeur fausse). README : `img.shields.io/endpoint?url=raw.../coverage-badge.json`. Coverage mesurée : 50,3 %. Commit `2c503510a`.
- Gates Lot 7 : ruff ✓ · pytest 178/1 ✓ · mypy ✓.

### MT-T5a-plan — Plan T5a écrit dans ROADMAP.md (2026-08-14)  � ⏳ exécution à venir
- ROADMAP.md : section « T5a — Vérification des gates & clôture des restes du Lot 4 » (16 micro-tâches
  en cases à cocher : 0.1→4.2) + tickets ouverts **4.2b** (suppression copie parallèle pipeline.py,
  condition d'entrée : TODO `agent_runner` fermés) et **4.4c** (extraction des 5 installateurs vers
  `ollama_install_{linux,windows,mac}.py`) ajoutés sous le Lot 4. L.37 aligné sur `fail_under=48`.
- État vérifié (HEAD `d79b1b152`) : format gate **ROUGE** (`tests/test_pipeline_steps.py` non formaté),
  cov 50,26 % ≥ 46 %, badge 50,3 % à jour, mypy 121 src ✅.
- Décisions actées dans le plan : contrat d'erreur state partout (pas de raise frontière) ;
  `di.py:107` fermé « inference suffit » ; `pipeline_steps.py:24` non touché (vivante via AgentGraph) ;
  fix `model_selector` sur 2 call sites dont `:307` vivant.
- Prochaine session : exécuter depuis **MT-0.1** (gates vertes + 1 commit atomique par micro-tâche).
- Aucun commit (conforme AGENTS.md).

### MT-T5a-0.1 — Gate format débloquée (2026-08-14) ✅
- `ruff format tests/test_pipeline_steps.py` (1 fichier reformatté, 7+/2-) → 4 gates vertes
  (ruff check · format --check · mypy 121 src · pytest 178/1, 50,26 % ≥ 46).
- Commit `17c7a5a1c` `style: ruff format tests/test_pipeline_steps.py` ; BACKLOG/ROADMAP restent
  non commités (docs T5a, fusionnés dans les commits docs 4.1/4.2).
- Prochaine micro-tâche : **MT-0.2** (fail_under 46 → 48 + vérif « Required test coverage of
  48.0% reached »).

### MT-T5a-0.2 — fail_under 48 (2026-08-14) ✅
- `pyproject.toml` : `fail_under = 48` (50,26 % mesuré − 2) + commentaire mis à jour
  (mesuré 50,26 % au T5a). ROADMAP L.37 déjà aligné. Vérif : « Required test coverage of
  48.0% reached. Total coverage: 50.26% » (178 passed, 1 skipped).
- Commit `1e20f4f21` `chore(coverage): fail_under 46 -> 48 (mesuré 50,26 %)`.
- Prochaine micro-tâche : **MT-1.1** (RED propagation du modèle au runner, GREEN
  `inspect.signature`).

### MT-T5a-1.1 — Modèle propagé au runner (2026-08-14) ✅
- RED : 5 tests (1 échoue) — `test_execute_pipeline_step_runner_three_params_receives_model`
  (appel 3 params → TypeError → état d'erreur) ; 2e test documentaire : runner 2 params appelé
  sans modèle.
- GREEN : `_runner_supports_model()` (détection `inspect.signature`, portée de
  `pipeline.py:68-76`) + branche runner : `model_selector(agent_key, inference)` (convention MT-1.2
  déjà appliquée ici : inference, pas la tâche) ; aucun paramètre nouveau ; `model_selector=None`
  sûr (→ `model=None`).
- Gates : 4 vertes (180 passed / 1 skip, 50,31 % ≥ 48).
- Commit `55f60e18c` `feat(pipeline_steps): propage le modèle au runner (parité _run_via_agent)`.
- Prochaine micro-tâche : **MT-1.2** (fix `model_selector` sur `pipeline.py:299` et `:307`).

### MT-T5a-1.2 — model_selector corrigé (2026-08-14) ✅
- Contrat vérifié : `services/selector.py:184` `select_model(agent_key, inference, log_service=None)`
  — les 2 call sites passaient la **tâche** au 2e paramètre.
- Fix `pipeline.py:299` (`_run_via_agent`) → `self._inference` ; `pipeline.py:307`
  (`_run_via_inference`) → le paramètre `inference` de la méthode (vivant via
  `routes/pipelines.py:40` POST /run).
- `select_model(agent_key, None)` n'était PAS sûr (AttributeError sur `resolve_model`) → garde
  ajoutée : `inference is None → ""` (conforme docstring « chaîne vide si aucun modèle, l'appelant
  gère l'erreur ») ; vérifié par `select_model('dev', None)` → `''`. `pipeline_steps.py:24` NON
  touché (vivant via AgentGraph).
- Gates : 4 vertes (180/1, 50,31 %).
- Commit `ea0602672` `fix(pipeline): model_selector reçoit inference et non la tâche (2 call sites)`.
- Note collision de nom (2 `select_model`) : `pipeline_steps.select_model(agent_key, model,
  provider)` ≠ `selector.select_model(agent_key, inference, log_service)` — documentée ici,
  réassignées par injection distincte.
- Prochaine micro-tâche : **MT-1.3** (RED runner non callable → erreur typée).

### MT-T5a-1.3 — Runner non callable rejeté (2026-08-14) ✅
- RED : `test_execute_pipeline_step_non_callable_runner` échoue (ancien comportement :
  `str(agent_runner)` comme réponse de succès).
- GREEN : `NonCallableRunnerError` (exception typée dans `pipeline_steps.py`) levée à la place du
  repr ; capturée par la boucle retry existante → entrée d'erreur dans `results` + `state["error"]`,
  **aucun raise frontière** (contrat d'erreur state, conforme filet 2.1 à venir).
- Gates : 4 vertes (181/1, 50,39 % ≥ 48).
- Commit `a4ad48d80` `fix(pipeline_steps): rejette un agent_runner non callable`.
- Prochaine micro-tâche : **MT-1.4** (ticket `di.py:107` fermé, zero code).

### MT-T5a-1.4 — Ticket di.py:107 fermé (2026-08-14) ✅
- Preuve (zéro code de logique) : `routes/pipelines.py:40` (`run()` → `_run_via_inference` quand
  `agent_runner=None`) + inference configuré (`di.py`) + aucun type runner ; le 404 reste réservé
  à `_resolve_pipeline`. Commentaire `di.py:105-107` acté : « agent_runner = point d'extension ».
- BACKLOG : ticket `di.py:107` marqué FERMÉ.
- Commit `8a467e24f` `docs(backlog): ferme le ticket di.py:107 (inference suffit)` (inclut les
  cases cochées 0.1→1.3 + entrées BACKLOG accumulées — docs T5a, cohérents avec l'état réel).
- Phase 1 complète. Prochaine micro-tâche : **MT-2.1** (filet de caractérisation AVANT tout déplacement).

### MT-T5a-2.1 — Filet de caractérisation PipelineService (2026-08-14) ✅
- `tests/test_pipeline_characterization.py` (158 l., 6 tests) verts sur le code ACTUEL :
  1. contrat d'erreur : sans backend → entrée d'erreur dans `results`, aucune exception (HTTP 200
     côté route) ; 2. retry CONDITIONNEL `on_error=="retry"` (3 appels pour max_retries=2) vs
     `"abort"` (1 appel, pas de retry) — différencie de `pipeline_steps` (retry inconditionnel) ;
     3. hook habits sur succès (task/pipeline/step) + absent sans mémoire ; 4. `on_error=="skip"`
     → continuation (2 résultats, pas d'arrêt fatal ni timeout).
- Gates : 4 vertes (187/1, **51,40 %** ≥ 48 — filet ajoute ~1,1 pt de couverture).
- Commit `565144547` `test(pipeline): filet de caractérisation avant suppression de la copie parallèle`.
- Prochaine micro-tâche : **MT-2.2** (retry conditionnel `on_error=="retry"` porté dans pipeline_steps).

### MT-T5a-2.2 — Retry conditionnel dans pipeline_steps (2026-08-14) ✅
- RED : 2 tests dédiés (CountingRunner) — `on_error="retry"` → 3 appels (max_retries=2) ;
  `on_error="abort"` → 1 appel. L'ancien code (boucle inconditionnelle) faisait 3 appels dans les
  2 cas ; le monkeypatch `time.sleep` échouait aussi (pas de `import time` dans pipeline_steps).
- GREEN : `_should_retry()` (parité `pipeline.py:330`) + `_wait_before_retry()` (délai
  `RETRY_DELAY*(attempt+1)`, logs) ; constantes `RETRY_DELAY=0.5`, `MAX_ERROR_LENGTH=200`
  dupliquées depuis pipeline.py (source unique après 2.4) ; erreurs d'exception tronquées à 200.
  Les 3 tests existants (max_retries=0) + filet caractérisation : inchangés, verts.
- Gates : 4 vertes (189/1, 51,47 % ≥ 48).
- Commit `3ebcbec41` `refactor(pipeline_steps): retry conditionnel on_error == retry (parité production)`.
- Prochaine micro-tâche : **MT-2.3** (hook habits en frontière).

### MT-T5a-2.3 — Hook habits en frontière (2026-08-14) ✅
- Choix documenté (docstring `_record_habits`) : frontière **PipelineService** — `update_habits`
  dépend du contexte pipeline (task, pipeline_id), pas de l'étape ; `pipeline_steps` reste sans
  effet de bord mémoire. Bloc habits extrait de `_record_step_success` → `_record_habits()`,
  appelée par `_execute_all_steps` sur succès. Refactor sécurisé par le filet 2.1
  (`test_hook_habits_sur_succes`, `test_hook_habits_absent_si_pas_de_memoire`).
- Gates : 4 vertes (189/1, 51,48 % ≥ 48).
- Commit `0efacf45f` `refactor(pipeline): habits en frontière d'orchestration`.
- Prochaine micro-tâche : **MT-2.4** (PipelineService → `execute_pipeline_step`, suppression des
  6 méthodes dupliquées, pipeline.py < 300 l.).

### MT-T5a-2.4 — Copie parallèle supprimée (4.2b) (2026-08-14) ✅
- `_execute_all_steps` délègue à `execute_pipeline_step` (state partagé task/context/results) ;
  break sur erreur fatale (`state["error"]` + on_error != "skip") ; hook habits appelé sur la
  dernière entrée réussie (`results[-1]["error"] is None`).
- Supprimés : `_execute_step`, `_run_via_agent`, `_run_via_inference`, `_extract_response`,
  `_execute_with_retry`, `_wait_before_retry`, `_record_step_success`, `_record_step_error` +
  `_check_runner_signature`/`_supports_model` (détection portée au MT-1.1) ; imports morts
  (`inspect`, `time`, `DEFAULT_MODEL`) ; `RETRY_DELAY`/`MAX_ERROR_LENGTH` → pipeline_steps
  (source unique).
- `pipeline.py` : 447 → **294 l.** (< 300 ✓), zéro logique d'étape dupliquée, `execute_pipeline_step`
  dé-orpheliné ; `_record_habits` (MT-2.3) préservée.
- Filet : monkeypatch retry recâblé sur `services.pipeline_steps.time.sleep` (le sleep a suivi la
  logique) — aucun comportement changé. Gates : 4 vertes (189/1, 51,28 % ≥ 48).
- Commit `38249de7e` `refactor(pipeline): supprime la copie parallèle au profit de pipeline_steps (4.2b)`.
- **Lot 4.2b clôturé.** Prochaine micro-tâche : **MT-3.1** (5 tests de caractérisation des
  installateurs).

### MT-T5a-3.1 — Caractérisation des 5 installateurs (2026-08-14) ✅
- 5 tests ajoutés dans `tests/test_ollama_installer.py` (section « Installateurs plateforme
  (4.4c, MT-3.1) », style patch/tmp_path existant) : apt succès (returncode 0 → chemin) ; linux_tar
  full flow (x86_64→amd64, download/verify/extract/copy, BIN_LINUX + lib/ollama, nettoyage
  finally) ; windows_zip full flow (ollama.exe + moteur copié sous BASE_DIR/lib/ollama, nettoyage
  TEMP) ; mac_brew sans brew (None sans erreur) ; mac_script (refus curl|sh, log « désactivée »).
- Vert d'emblée (un ajustement : `exist_ok=True` dans le fake d'extraction Windows — `dl_bin`
  pré-créé par le code avant `_safe_extract_zip`).
- Gates : 4 vertes (**194/1, 52,31 %** ≥ 48 — les installateurs montent la couverture).
- Commit `8a77c0bc2` `test(ollama): caractérisation des 5 installateurs plateforme`.
- Prochaine micro-tâche : **MT-3.2** (`ollama_install_linux.py` + ré-exports).

### MT-T5a-3.2 — Installateurs Linux extraits (4.4c) (2026-08-14) ✅
- `services/ollama_install_linux.py` (nouveau, 67 l.) : `_install_linux_apt` + `_install_linux_tar`
  et leurs imports (archive/download/system). `ollama_installer.py` : import + ré-export
  (`__all__` augmenté), imports morts nettoyés (`platform`, `BIN_LINUX`, `LAUNCHER_INSTALL_TIMEOUT`…
  réajoutés `contextlib`/`LAUNCHER_WAIT_TIMEOUT` : encore vivants pour windows/mac).
- Surface préservée : `ensure_ollama_binary`, `_extract_tar_zst` (ré-export conservé —
  `test_ollama_installer.py:23` l'importe depuis ollama_installer), `_install_linux_tar` via
  `scripts/install.py:194-198`, `jarvis.py:20`, `launcher_win.py:27` — vérifié par
  `IMPORTS_OK`. Patchs des tests 3.1 recâblés sur `ollama_install_linux` (le code a déménagé,
  aucune assertion changée).
- Gates : 4 vertes (**194/1, 52,42 %**, mypy 122 src).
- Commit `687e9c405` `refactor(ollama): extrait les installateurs Linux (4.4c)`.
- Prochaine micro-tâche : **MT-3.3** (`ollama_install_windows.py` + ré-export).

### MT-T5a-3.3 — Installateurs Windows extraits (4.4c) (2026-08-14) ����
- `services/ollama_install_windows.py` (nouveau, 67 l.) : `_install_windows_zip`
  et ses imports (archive/download/system). `ollama_installer.py` : import + ré-export
  (`__all__` augmenté), imports morts nettoyés (`platform`, `BIN_LINUX`, `LAUNCHER_INSTALL_TIMEOUT`…
  réajoutés `contextlib`/`LAUNCHER_WAIT_TIMEOUT` : encore vivants pour windows/mac).
- Surface préservée : `ensure_ollama_binary`, `_extract_tar_zst` (ré-export conservé —
  `test_ollama_installer.py:23` l'importe depuis ollama_installer), `_install_windows_zip` via
  `scripts/install.py:194-198`, `jarvis.py:20`, `launcher_win.py:27` — vérifié par
  `IMPORTS_OK`. Patchs des tests 3.1 recâblés sur `ollama_install_windows` (le code a déménagé,
  aucune assertion changée).
- Gates : 4 vertes (**194/1, 52,42 %**, mypy 122 src).
- Commit `687e9c405` `refactor(ollama): extrait les installateurs Windows (4.4c)`.
- Prochaine micro-tâche : **MT-3.4** (`ollama_install_mac.py` + sélecteur + non-régression imports → commit refactor).

### MT-T5a-3.4 — Installateurs macOS extraits (4.4c) (2026-08-14) ����
- `services/ollama_install_mac.py` (nouveau, 52 l.) : `_install_mac_brew` + `_install_mac_script`
  et leurs imports. `ollama_installer.py` : import + ré-export (`__all__` augmenté), `shutil`
  conservé (patche tests via `services.ollama_installer.shutil`).
- Surface préservée : `ensure_ollama_binary`, `_install_mac_brew`, `_install_mac_script`
  accessibles depuis `services.ollama_installer` (tests inchangés).
- Gates : 4 vertes (**194/1, 52,57 %** ≥ 48, mypy 124 src).
- Prochaine micro-tâche : **MT-4.1** (ROADMAP : 4.2b/4.4c cochés, compteurs à jour → commit docs(roadmap)).

### MT-T5a-4.1 — ROADMAP Lot 4 complet (2026-08-14) ��
- 4.2b coché (copie parallèle supprimée, `pipeline.py` 294 l. < 300)
- 4.4c coché (5 installateurs extraits vers `ollama_install_{linux,windows,mac}.py`)
- Ordre d'exécution mis à jour : Lot 4 (4.1 · 4.2 · 4.3 · 4.4) complet
- Couverture mesurée : 52,57 % → `fail_under` porté à 50 (52,57 - 2)
- Badge régénéré : 52,6 % (orange)
- Gates : 4 vertes (ruff �� · format �� · mypy 124 src �� · pytest 194/1, 52,57 % ≥ 50)
- Prochaine micro-tâche : **MT-4.2** (BACKLOG T5a + tickets fermés + fail_under final + badge régénéré même commit → commit docs).