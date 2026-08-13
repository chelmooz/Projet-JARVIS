# BACKLOG — JARVIS Portable

Journal des micro-tâches + décisions. Mis à jour après chaque micro-tâche.

## ROADMAP active
`ROADMAP_CONSOLE.md` — Console Tab (9ᵉ onglet) + Command Palette (Ctrl+K).

## Micro-tâches

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
