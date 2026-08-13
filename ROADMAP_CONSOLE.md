# ROADMAP — Console Tab + Command Palette (Ctrl+K)

**Projet** : JARVIS Portable (FastAPI + frontend vanilla ES modulaire, 100% offline)
**Objectif** : ajouter un 9ᵉ onglet SPA « Console » (commandes `@agent tâche` → `/api/jarvis`)
+ une palette globale Ctrl+K/Cmd+K (autocomplétion `@agent`) + handoff Palette → Console.
**Statut** : plan figé, prêt à exécuter par micro-tâches (MT).

---

## 0. Contexte vérifié sur le dépôt réel (à lire en premier dans la nouvelle session)

Vérifié empiriquement le 13/08/2026 avant fige du plan :

- `escHtml()` **existe déjà** dans `static/assets/js/modules/utils.js:5` (exporté, utilisé partout). → Ne pas l'extraire.
- **Pas de map `AGENT_COLORS`** dans le dépôt. Les badges agent passent par les classes CSS
  `badge badge-agent` / `badge badge-model` (cf. `chat.js:102`, `conversations.js:71`). → Réutiliser ce mécanisme, pas de 2ᵉ système.
- **Pas de `pollStatus()`**. Le statut passe par `connectStatusSSE()` dans `static/assets/js/modules/status.js:12`
  (ouvre `EventSource('/api/status/stream')`, manipule le DOM directement dans `onmessage`, **sans** `CustomEvent`).
  Il existe `pollMetrics()` (`status.js:34`) — différent, ne pas confondre.
- Front actuel : **8 onglets** SPA (`index.html`, `tab-btn` + `tab-content` génériques via `data-tab` dans `app.js:43-46`),
  **modules ES** sous `static/assets/js/modules/`, wiring dans `boot.js`.
- **Infra de test présente** : `static/package.json` (`vitest run`, jsdom), `static/vitest.config.js`,
  `static/test/chat.test.js` + `static/test/vision.test.js`. → Le TDD est faisable (contrairement à l'hypothèse
  « pas de tests » du doc corrigé Lovable, qui était fausse).
- `GET /api/agents` existe (`controllers/routes/agents.py:68`) → renvoie `{profiles, agent_model_map}`.
- `POST /api/jarvis` existe (`controllers/routes/jarvis.py:113`) → `JarvisRequest` (`task`, `image`, `conversation_id`).
- Routage `@command` : `config/agent_routing.yaml` route sur les **routing keys**
  `@cyber/@dev/@network/@hardware/@vision` (+ alias `@orchestrateur→dev`, `@datasecu→cyber`…).
  `/api/agents` renvoie les **clés de profil** (`orchestrateur/techlead/devops/designer/datasecu`) — mismatch à réconcilier (voir MT-1.5).
- `.gitignore:2 = models/` : latité sur clone frais (exclurait `models/schemas.py`). Non bloquant en local
  (déjà tracké). Correctif 1 ligne hors scope (voir §5).

### Livrable Lovable = NOGO en tant que code
Template React/TanStack : ne peut pas exécuter FastAPI. Ses fichiers JS sont des **brouillons non fiables**
à ré-implémenter proprement selon les patterns du dépôt. `PLAN.md` (vitest complet, `AGENT_COLORS`, `pollStatus`)
contredit le doc corrigé → **ne suivre QUE le doc corrigé** (ci-dessous). Marquer `PLAN.md` obsolète si présent.

---

## 1. Décisions figées

| # | Décision | Raison |
|---|----------|--------|
| 1 | Champ `source: 'chat'\|'console'\|'palette'` **gardé** sur `JarvisRequest` | Utile analytics, cheap, non-breaking (défaut `'chat'`) |
| 2 | **DRY** : `GET /api/agents` renvoie `routing_prefixes` (lecture `agent_routing.yaml`) | Évite de dupliquer la config des tokens côté client |
| 3 | Vérif **manuelle F12** acceptée (pas de suite de tests exhaustive) | Conforme à la contrainte « pas de tests à raloonge » ; tests vitest **focused** sur la logique pure uniquement |

---

## 2. Garde-fous d'exécution

- **Aucun commit** sans accord explicite (prévalent sur le RTOC) — coder + vérifier, s'arrêter avant le commit.
- **TDD-lite** : 1 test focused par logique pure (vitest/jsdom, gabarit `static/test/chat.test.js`),
  DOM vérifié au F12. Pas de suite exhaustive.
- **Refactor > patch** sur chaque fichier existant touché (`status.js`, `boot.js`, `index.html`, `schemas.py`, `jarvis.py`, `agents.py`).
- Strictement **additif** : la Console vit dans ses propres fichiers ; l'existant ne reçoit que les insertions listées.
- Zéro nouvelle route (hors le champ `source` + `routing_prefixes` qui sont des extensions non-breaking d'endpoints existants).
- Zéro nouvelle dépendance npm/pip.

---

## 3. Arborescence cible

```
static/assets/js/modules/console-client.js     (A — fetch /api/jarvis + /api/agents, parsing @agent, cache, store)
static/assets/js/modules/command-palette.js    (B — overlay Ctrl+K + autocomplétion)
static/assets/js/modules/console-tab.js        (C — 9ᵉ onglet, scrollback, historique)
static/assets/css/console.css                 (styles Console/Palette, tokens existants)
static/partials/command-palette.html           (markup overlay, injecté au boot)  [ou inline dans console-tab.js]
models/schemas.py                              (+ champ source sur JarvisRequest)
controllers/routes/jarvis.py                   (lit + propage source)
controllers/routes/agents.py                   (GET /api/agents renvoie routing_prefixes)
static/assets/js/modules/status.js             (1 ligne : émet jarvis:status-updated)
static/assets/js/modules/boot.js               (wiring Ctrl+K global + init palette + console)
static/index.html                              (9ᵉ tab-btn + #tab-console + <link> console.css)
README.md                                      (section Console/Palette)
```

---

## 4. Micro-tâches (ordre d'exécution)

**MT-0 — Recon (non-code, déjà faite)** : `agent_routing.yaml` confirmé → la Console utilise les **routing keys**.

**MT-1 — A0 backend (seul touch backend « source »)**
- `models/schemas.py` : `source: Optional[Literal['chat','console','palette']] = 'chat'` sur `JarvisRequest`.
- `controllers/routes/jarvis.py` : lire `body.source`, le propager (analytics optionnel).
- Vérif : `curl -X POST /api/jarvis` sans `source` → 200, comportement inchangé.

**MT-1.5 — DRY (routing_prefixes)**
- `controllers/routes/agents.py` (`list_profiles`/`GET /api/agents`) : ajouter `routing_prefixes` (lecture `config/agent_routing.yaml`, 1 ligne). Non-breaking (champ en plus).
- Vérif : `GET /api/agents` contient `routing_prefixes: ["@cyber","@dev",...]`.

**MT-2 — A `console-client.js` (module pur, zéro DOM)**
- `parseCommand(input)` : regex `^@(\w+)\s+(.*)$` → `{agent, task}` ; erreur explicite si invalide (jamais `undefined` silencieux).
- `sendCommand(cmd)` : `POST /api/jarvis` avec `{task, source}` → `{ok, data, error}` ; `AbortController` 30 s ;
  normalise 5xx / réseau / timeout en `{ok:false, error}` sans throw.
- `fetchAgents()` : liste `{key, name, model}` depuis `/api/agents` via `cachedFetch()` (`utils.js`).
- Store mémoire singleton `lastCommand` pour le handoff (MT-5).
- Tests focused : `parseCommand` (valide/invalide), `sendCommand` (erreur réseau mockée), `fetchAgents` (mapping).

**MT-3 — B `command-palette.js`**
- Ctrl+K / Cmd+K global → overlay visible + focus input (listener monté dans `boot.js`).
- Saisie `@` → dropdown agents filtré par préfixe (via `fetchAgents()`), rendu échappé `escHtml`.
- Entrée → `sendCommand()` + résultat inline (`source:'palette'`).
- Échap → fermer + vider champ + restaurer focus.
- Bouton « Ouvrir en Console » → handoff.
- Tests focused : toggle overlay, autocomplétion, submit, Escape.

**MT-4 — C `console-tab.js` + `index.html`**
- `index.html` : 9ᵉ `<button class="tab-btn" data-tab="console">` + `<div class="tab-content" id="tab-console">` + `<link>` `console.css`.
- submit → entrée scrollback append-only + badge agent (`badge-agent`/`badge-model` via `escHtml`).
- ↑/↓ historique depuis `localStorage['jarvis_console_history']` (max 50 ; réponses jamais persistées).
- indicateur de connexion alimenté par `jarvis:status-updated`.
- Tests focused : scrollback append, navigation historique.

**MT-5 — D handoff Palette → Console**
- `store.lastCommand` → bascule d'onglet + pré-remplissage scrollback/input. Zéro nouvelle route, zéro dépendance.

**MT-6 — status.js (1 ligne)**
- Fin d'`onmessage` de `connectStatusSSE()` : `document.dispatchEvent(new CustomEvent('jarvis:status-updated', { detail: s }))`.
- Refactor seulement si le bloc grossit.

**MT-7 — boot.js (wiring)**
- Unique listener `keydown` Ctrl+K/Cmd+K sur `document` (monté une fois, actif partout) + init palette + console.

**MT-8 — README.md**
- Section Console/Palette dans les fonctionnalités + guide pas-à-pas, au niveau de détail de l'onglet Outils.

**MT-9 — Finalisation**
- Vérif manuelle F12 (`launchers/JARVIS.bat` en local) : pas d'erreur JS, requêtes `/api/jarvis` + `/api/agents`,
  Ctrl+K fonctionnel, 9ᵉ onglet. `git status` + `git clean -n` vides, aucun artefact de debug laissé.

---

## 5. Hors scope (V1)

- CLI native terminal (ticket séparé).
- Persistance du scrollback complet (ticket séparé, s'appuyer sur `/api/conversations`).
- Auth / permissions par commande.
- xterm.js / PTY (rejeté, voir RFC §3).
- **Correctif `.gitignore`** : `models/` → `models/ollama/` (scoper sur les poids uniquement). 1 ligne, à faire à part, signalé.

---

## 6. Checklist de reprise (nouvelle session)

- [ ] Relire ce ROADMAP + `config/agent_routing.yaml` + `static/assets/js/modules/utils.js` (`escHtml`, `cachedFetch`).
- [ ] Confirmer que le dépôt tourne (`python jarvis.py` ou `launchers/JARVIS.bat`).
- [ ] MT-1 → MT-9 dans l'ordre ; 1 commit UNIQUEMENT si accord explicite.
- [ ] Skills à invoquer : `test-driven-development` (par MT), `verification-before-completion` (avant tout claim).
