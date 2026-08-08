# PLAN.md — Console Tab + Command Palette (Ctrl+K)

**Références** : RFC-2026-08-console-cli + Addendum Q1-Q9 (tranché en session, mode Plan).
**Statut** : PRÊT À EXÉCUTER — TDD strict (RED → GREEN → REFACTOR par tâche).
**Branche suggérée** : `feat/console-cli` (worktree).

---

## 1. Décisions d'architecture (Addendum, résumé exécutif)

| Q | Décision | Conséquence implémentation |
|---|----------|---------------------------|
| 1 | 9ᵉ onglet SPA (pas de `console.html`) | `index.html` : bouton sidebar + `#tab-console` |
| 2 | Ctrl+K global (document) monté dans `boot.js` | Un seul listener, actif partout |
| 3 | Store en mémoire (ES module singleton) pour le handoff Palette→Console | Pas de query param, pas de localStorage |
| 4 | Historique commandes persisté en localStorage (max 50), scrollback (réponses) volatile | Réponses `@cyber` = données sensibles → jamais persistées en V1 |
| 5 | Tests unitaires `console-client.js` (mock fetch) + DOM limité (ouverture, soumission, autocomplétion) | Pattern `chat.test.js` |
| 6 | Réutiliser `pollStatus()` + `CustomEvent('jarvis:status-updated')` | Pas de 2ᵉ polling vers `/api/status` |
| 7 | `escHtml()` extrait dans `static/assets/js/modules/utils.js` | Une seule source de vérité |
| 8 | Cache agents TTL 60s dans `console-client.js` | Partagé Palette/Console |
| 9 | Champ optionnel `source: 'chat'|'console'|'palette'` sur `POST /api/jarvis` (défaut `'chat'`) | Non-breaking, utile analytics |

---

## 2. Arborescence cible

```
static/
├── assets/js/modules/
│   ├── console-client.js          (A — fetch /api/jarvis + /api/agents + parsing + cache 60s)
│   ├── command-palette.js         (B — overlay Ctrl+K + autocomplétion)
│   ├── console-tab.js             (C — 9ᵉ onglet, scrollback, historique ↑/↓)
│   └── utils.js                   (escHtml() extrait de app.js + AGENT_COLORS)
├── partials/
│   └── command-palette.html       (markup overlay, injecté au boot)
├── test/
│   ├── console-client.test.js     (A)
│   ├── command-palette.test.js    (B)
│   └── console-tab.test.js        (C)
models/
├── schemas.py                     (+ champ `source` optionnel dans JarvisRequest)
controllers/routes/
├── jarvis.py                      (+ lecture + propagation `source`)
```

---

## 3. Bloc A0 — Schéma backend `source` (avant A1)

| # | Action | Test de vérification |
|---|--------|----------------------|
| A0.1 | `models/schemas.py` : `source: Optional[Literal['chat','console','palette']] = 'chat'` | `pytest tests/test_api_contract.py -q` |
| A0.2 | `controllers/routes/jarvis.py` : propager `source` dans le flux (analytics optionnel) | `pytest tests/test_api.py::TestJarvisRoute -q` |
| A0.3 | Non-régression : `POST /api/jarvis` sans `source` → 200, comportement inchangé | `curl` / test existant |

---

## 4. Bloc A — `console-client.js` (module partagé)

| # | Cycle | Action | Test |
|---|-------|--------|------|
| A1 | RED | `fetchAgents()` retourne liste `{name, model, color}` parsée de `/api/agents` | `npm test -t fetchAgents` (échoue) |
| A2 | GREEN | fetch + mapping + cache TTL 60s (Q8) | passe |
| A3 | RED | `sendCommand()` extrait `@agent` (regex `^@(\w+)\s+(.*)$`), POST `/api/jarvis`, retourne `{ok, data, error}` | `npm test -t sendCommand` (échoue) |
| A4 | GREEN | implémentation + fallback sans agent | passe |
| A5 | RED | erreur réseau / HTTP 5xx / timeout → `{ok:false, error}` sans throw | `npm test -t error` (échoue) |
| A6 | GREEN | try/catch + AbortController (30 s) + normalisation | passe |
| A7 | REFACTOR | extraire `AGENT_COLORS` → `utils.js` ; badge agent rendu via `renderAgentBadge()` partagé (Q7) | `npm test` |

---

## 5. Bloc B — Command Palette (Ctrl+K)

| # | Cycle | Action | Test |
|---|-------|--------|------|
| B1 | RED | Ctrl+K / Cmd+K (global) → overlay visible + focus input | `npm test -t "Ctrl+K"` (échoue) |
| B2 | GREEN | listener `keydown` sur `document` (monté dans `boot.js`) + toggle `.show` | passe |
| B3 | RED | saisie `@` → dropdown agents (via `fetchAgents()`) filtré sur préfixe | `npm test -t "autocompletion"` (échoue) |
| B4 | GREEN | event `input` → filtre + render liste (échappé `escHtml`) | passe |
| B5 | RED | Entrée → `sendCommand()` + résultat inline (Q5 : test DOM limité) | `npm test -t "submit"` (échoue) |
| B6 | GREEN | brancher `sendCommand()` + render résultat (échappé) | passe |
| B7 | RED | Échap → fermer + vider champ + restaurer focus | `npm test -t "Escape"` (échoue) |
| B8 | GREEN | keydown Escape → hide + clear | passe |
| B9 | REFACTOR | extraire widget Overlay réutilisable (prop `prefillCommand` pour D) | `npm test` |

---

## 6. Bloc C — Onglet Console (9ᵉ onglet SPA)

| # | Cycle | Action | Test |
|---|-------|--------|------|
| C1 | RED | bouton sidebar « Console » présent + onglet affiché | `npm test -t "onglet"` (échoue) |
| C2 | GREEN | markup index.html (sidebar + `#tab-console`) | passe |
| C3 | RED | commande soumise → entrée scrollback + badge agent coloré | `npm test -t "scrollback"` (échoue) |
| C4 | GREEN | append-only + meta badge (via renderer partagé) | passe |
| C5 | RED | historique ↑/↓ dans l'input | `npm test -t "historique"` (échoue) |
| C6 | GREEN | `localStorage['jarvis_console_history']` (max 50, Q4) + navigation | passe |
| C7 | RED | indicateur connexion reflète `/api/status` | `npm test -t "status"` (échoue) |
| C8 | GREEN | écoute `CustomEvent('jarvis:status-updated')` émis par `pollStatus()` (Q6) | passe |
| C9 | REFACTOR | badge agent dédupliqué via module partagé (Q7) | `npm test` |

---

## 7. Bloc D — Handoff Palette → Console

| # | Cycle | Action | Test |
|---|-------|--------|------|
| D1 | RED | dans la Palette, « Ouvrir en Console » → switch d'onglet + pré-remplissage scrollback/input | `npm test -t "handoff"` (échoue) |
| D2 | GREEN | store mémoire du module (`consoleClient.lastCommand`) (Q3) + bascule d'onglet | passe |
| D3 | REFACTOR | revue finale — zéro nouvelle route, zéro dépendance ajoutée | suite complète |

---

## 8. Protocole de vérification (checkpoints)

| CP | Commande | Critère |
|----|----------|---------|
| CP1 | `cd static && npm test` | 100 % suite vitest |
| CP2 | `cd .. && pytest tests/test_api.py tests/test_schemas.py -q` | vert |
| CP3 | `pytest tests/test_agents.py -q` | vert |
| CP4 | `cd static && npm test` entier (régression chat/vision) | vert |
| CP5 | Serveur réel : `python jarvis.py` + manuel (Ctrl+K, onglet) | fonctionnel |

---

## 9. Ordre d'exécution

```
A0 → A1..A7 (console-client + utils)
   → B1..B9 (palette, dépend A)
   → C1..C9 (onglet console, dépend A + event status)
   → D1..D3 (handoff, dépend B + C)
   → CP1..CP5
```
Commit après chaque cycle RED→GREEN→REFACTOR (message `feat(console): ...`).

---

## 10. Points hors scope (V1)

- CLI native terminal (ticket backlog séparé)
- Persistance du scrollback complet (s'appuyer sur `/api/conversations` si besoin, ticket séparé)
- Authentification / permissions par commande
- xterm.js / PTY (rejeté, voir RFC §3)
