# BACKLOG — JARVIS Portable

Journal des micro-tâches + décisions. Mis à jour après chaque micro-tâche.

## ROADMAP active
`ROADMAP_CONSOLE.md` — Console Tab (9ᵉ onglet) + Command Palette (Ctrl+K).

## Micro-tâches

### MT-3 — ROADMAP TDD qualité (audit 68→90)  🔧 2026-08-13
- Créé `ROADMAP.md` à la racine : suivi à cocher des LOTS 0→7. Contrat TDD strict RED→GREEN→REFACTOR.
- **Lot 0 (verrou outillage) terminé & vert** : 0.1 mypy dans dev extras · 0.2 retrait exclude ruff ·
  0.3 fail_under=0 + retrait commentaire mesure fantôme · 0.4 workflow ci.yml (push/PR, 3.12/3.13) ·
  0.5 retrait badge Tests-478 · 0.6 ruff format (4 fichiers) · 0.7 mypy vert (typage SSE + vision + override rapidocr).
- Gate validée : `ruff check .` ✓ · `ruff format --check .` ✓ · `mypy` ✓ (119 src) · `pytest --cov` ✓ (4 passed, fail_under=0).
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
  (pyproject.toml) → pytest importe désormais le source local. ⚠️ À retenir : la copie site-packages est
  un snapshot obsolète du projet ; privilégier `pip install -e .` pour que le source local soit autoritatif.
- **Lot 3.1 (API santé) terminé** : `tests/test_api_health.py` (4 tests) — `/api/status` → 200
  dégradé offline + reflète le DI injecté ; `/api/health` → 503 dégradé / 200 sain.
  Injection de fakes via `app.state.context` (DI respecté). Gates : ruff ✓ · format ✓ ·
  mypy 119 src ✓ · pytest 124 passés / 1 skip ✓.
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
  Gates : ruff ✓ · format ✓ · mypy 119 src ✓ · pytest 131 passés / 1 skip ✓ · couv 47.8 % ≥ 46 %.
- **Lot 0 (reconcilié) + Hygiène terminés** : 0.4 ci.yml conforme · 0.5 badge Tests-478 absent ·
  0.6 exclude ruff absent · 0.7 `fail_under=46` (mesuré 48−2) · Hygiène1 site-packages
  désinstallé + install éditable · Hygiène2 `.gitignore` dist/ + ticket mypy scripts/ ·
  Hygiène3 `git fsck` OK (dangling seuls).
- **Lot 3.3 (API agents) terminé** : `tests/test_api_agents.py` (5 tests) — `GET /api/agents` 200
  (structure), `POST /api/agents/assign` 200 (assigne, fichiers isolés via tmp+monkeypatch),
  404 profil inconnu, 400 modèle invalide, 500 fichier profils absent. Gates : ruff ✓ · format ✓ ·
  mypy 119 src ✓ · pytest 136 passés / 1 skip ✓ · couv 48 % ≥ 46 %.
- **Lot 3.4 (API fichiers) terminé** : `tests/test_api_files.py` (4 tests) — list 200 dans le
  sandbox (config d'auth isolée en tmp), refus dossier non autorisé (fail-closed) et hors sandbox
  (`error_type=not_authorized`), lecture fichier inexistant (`Pas un fichier`). Gates : ruff ✓ ·
  format ✓ · mypy 119 src ✓ · pytest 140 passés / 1 skip ✓ · couv 48 % ≥ 46 %.
- **Lot 3.5 (API rate limit) terminé** : `tests/test_api_ratelimit.py` (2 tests) — sous quota 200 +
  en-têtes `X-RateLimit-Limit`/`Remaining` ; au-delà 429 + `retry_after` cohérent avec
  `Retry-After` (patch `MAX_REQUESTS=2` + reset état). Gates : ruff ✓ · format ✓ · mypy 119 src ✓ ·
  pytest 142 passés / 1 skip ✓ · couv 49 % ≥ 46 %.
- **Lot 3.6 (API RAG/recherche) terminé** : `tests/test_api_rag.py` (3 tests) — `GET /api/search`
  avec `FakeVector` injecté : 200 + résultats/pagination (total/count/limit/offset), 400 query vide,
  texte scrubbé préservé. Gates : ruff ✓ · format ✓ · mypy 119 src ✓ · pytest 145 passés / 1 skip ✓ ·
  couv 49 % ≥ 46 %.
- **LOT 3 COMPLET** (API & intégration, 3.1→3.6) : 17 nouveaux tests d'API, tous verts, DI via
  `app.state.context` respectée partout. Prochaine phase : **Lot 4 (refactors sous filet)**.
- Prochaine micro-tâche : Lot 4.1 (`services/vector.py` 578→facade déléguant à
  `vector_index/search/cache/stats/docs/embedder` — API publique identique, tests 3.6 restent verts).

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

### MT-1 — Backend champ `source` sur JarvisRequest  ✅ 2026-08-13
- `models/schemas.py` : `source: Literal["chat","console","palette"] = "chat"` (default non-breaking).
- `services/analytics.py` + `ports/__init__.py` : `track_query(..., source="chat")` kwarg non-breaking.
- `controllers/routes/jarvis.py` : lit `body.source`, propage aux 2 `_track_query` (JSON + SSE).
- Vérif (pré-déploiement, pas de serveur) : `JarvisRequest(task='hello').source == 'chat'`,
  explicite 'console' OK, import `controllers.routes.jarvis` OK. Comportement inchangé sans `source`.

### MT-1.5 — DRY `routing_prefixes` sur GET /api/agents  ✅ 2026-08-13
- `controllers/routes/agents.py` : réutilise `services/router.load_routing_config()` (pas de re-lecture YAML).
  `ROUTING_PREFIXES = list(...prefix_map.keys())` exposé dans la réponse `ok()` (champ en plus, non-breaking).
- Vérif : `ROUTING_PREFIXES == ['@cyber','@dev','@network','@hardware','@vision','@orchestrateur','@techlead','@devops','@designer','@datasecu']`.

### MT-2 — console-client.js (module pur, zéro DOM)  ✅ 2026-08-13
- `static/assets/js/modules/console-client.js` : `parseCommand` (regex + erreur explicite), `sendCommand`
  (POST /api/jarvis, AbortController 30 s, normalise 5xx/réseau/timeout en {ok,data,error}, jamais throw),
  `fetchAgents`/`agentsFromApi` (depuis /api/agents via cachedFetch), `consoleStore` singleton (handoff),
  `runCommand` convenience.
- Tests focused : `test/console-client.test.js` (16 tests, vitest/jsdom). `npm install` fait (réseau OK).
  Résultat : 16/16 pass.

### MT-3 — command-palette.js (overlay Ctrl+K)  ✅ 2026-08-13
- `static/assets/js/modules/command-palette.js` : classe `CommandPalette` (mount/open/close/toggle,
  autocomplétion filtrée sur `routing_prefixes` via `fetchAgents`, submit avec `source:'palette'`,
  Escape, bouton « Ouvrir en Console » → `handoff()` dispatch `jarvis:palette-handoff` + `consoleStore`).
- Tests focused : `test/command-palette.test.js` (9 tests). Résultat : 9/9 pass.

### MT-4 — console-tab.js + index.html (9ᵉ onglet)  ✅ 2026-08-13
- `static/index.html` : 9ᵉ `<button class="tab-btn" data-tab="console">`, `<div id="tab-console">`
  (scrollback + input + badge connexion), `<link>` console.css.
- `static/assets/js/modules/console-tab.js` : classe `ConsoleTab` (scrollback append-only, badge agent,
  historique localStorage `jarvis_console_history` ≤50, nav ↑/↓, `jarvis:status-updated` → badge connexion,
  `_onHandoff` bascule onglet + pré-remplissage).
- `static/assets/css/console.css` : styles Console + Palette (tokens existants réutilisés).
- `app.js` : focus `#console-input` à l'ouverture de l'onglet (additif).
- Tests focused : `test/console-tab.test.js` (7 tests). Résultat : 7/7 pass.

### MT-5 — Handoff Palette → Console  ✅ 2026-08-13
- `command-palette.js` (bouton « Ouvrir en Console » + `handoff()`) dispatch `jarvis:palette-handoff`
  + `consoleStore.setLast`. `console-tab.js` `_onHandoff` bascule onglet + pré-remplit + (re)exécute.
  Zéro nouvelle route, zéro dépendance. Couvert par les tests MT-3/MT-4.

### MT-6 — status.js (event)  ✅ 2026-08-13
- `static/assets/js/modules/status.js` : fin d'`onmessage` de `connectStatusSSE()` →
  `document.dispatchEvent(new CustomEvent('jarvis:status-updated', { detail: s }))`.

### MT-7 — boot.js (wiring)  ✅ 2026-08-13
- `static/assets/js/modules/boot.js` : `consoleTab.mount()`, `palette.mount()`, listener unique
  `keydown` Ctrl/⌘+K sur `document` → `palette.toggle()`. Expose `window.__jarvisPalette/Console`.

### MT-8 — Documentation  ✅ 2026-08-13
- `README.md` est l'index des ADR (pas un doc features) → section « Console Tab + Command Palette »
  ajoutée dans `CHANGELOG.md` (niveau détail onglet Outils) + guide pas-à-pas.

### MT-9 — Finalisation  ✅ 2026-08-13
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
- État global : v6.0, 9 onglets + Palette Ctrl/⌘+K.

### Connaisseances non traitées (gaps signalés, hors périmètre de cette passe)
- `GET /api/agents` : `agentsFromApi` renvoie `model: null` pour les clés de routage
  (`cyber/dev/network/hardware/vision`) car `agent_model_map` est indexé par profil
  (orchestrateur/techlead/…). Mismatch documenté dans ROADMAP_CONSOLE.md MT-0 ; à réconcilier
  côté backend (ex. liste `agents` résolue) si besoin.
- Revue architecture large (SOLID/skill `solid`) non faite : la base est saine, passage
  lint/tests verts ; refactoring profond non lancé pour éviter tout risque sur la base stable.
