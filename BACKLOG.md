# 📋 BACKLOG.md — Plan de Micro-Tâches TDD (audit du 25/07/2026)

**Projet** : JARVIS Portable Edition v5.4
**État réel vérifié** : 811+ tests passed / 0 failed / 40 skipped / 1 xfailed (805 + 6 nouveaux : 2 batch writes + 4 bench I/O)
**Méthode d'audit** : relecture du BACKLOG.md précédent + grep/lecture du code réel derrière chaque item + relance de la suite de tests + `git log`/`git status`
**Verdict global** : Phase 8 complétée (orjson + profiling + rapport). Restent 9.4 (dark mode), et docs 10.1-10.3.

---

## 🚨 0. Actions immédiates

### 0.1 ✅ Commit en attente — CLOSED (25/07/2026)
- **Commit** : `docs: aligne README suite au retrait de .opencode/` (`2283b6b`)

---

## ✅ Phase 7 — Sécurité

### 7.1 → 7.6 : confirmés CLOSED, comportement inchangé en code (RAS)

### 7.4 ✅ Error leakage — CLOSED (25/07/2026)
`jarvis.py`, `agents.py`, `conversations.py` : déjà propres (vérifié, rien à faire).

Fuite réelle trouvée et corrigée : **`controllers/routes/documents.py:83`** (`vectorize_conversations`) renvoyait `str(e)` brut au client dans `errors[]`.
- **RED** : `tests/test_security_error_leakage.py` (créé) — 2 tests : pas de fuite du message brut + log serveur avec `exc_info=True`
- **GREEN** : message générique côté client (`"Erreur interne lors de la vectorisation"`) + `_logger.error(..., exc_info=True)` côté serveur
- **Preuve** : suite complète 805 passed / 0 failed / 40 skipped / 1 xfailed (vs 803 avant, +2 = les nouveaux tests)
- **Commit** : `fix(security): masque le détail d'exception brut dans vectorize_conversations (documents.py)` (`7747ad2`)

**`controllers/routes/pipelines.py:40`** : revu, non retenu comme fuite — `PipelineError` ne contient que des messages métier contrôlés (ex. `"Pipeline 'xyz' introuvable"`), aucun détail interne (chemin, stack, requête). Rien à faire.

---

## ⚡ Phase 8 — Performance (orjson + profiling) — COMPLÉTÉE

### 8.0 ✅ Outillage & Baseline — DONE (26/07/2026)
`scripts/profile_app.py` (cProfile endpoint profiling) et `scripts/bench_runner.py` (I/O benchmark runner) créés.

### 8.1 ✅ Inférence Ollama — connection pooling — DÉJÀ FAIT
Déjà en production dans `ollama_adapter.py` (`httpx.Client(timeout=...)` singleton).

### 8.2 ✅ Vector Search — numpy vectorisé — DÉJÀ FAIT
Déjà en production dans `vector_search.py` (`np.argpartition` + `np.argsort`).

### 8.3 ✅ Vector Cache — LRU borné — DÉJÀ FAIT
Déjà en production dans `vector_cache.py` (`OrderedDict` + TTL 300s).

### 8.4 ✅ I/O `orjson` + batch writes — DONE (26/07/2026)
- **RED** : `tests/test_io_perf.py` créé (4 benchmarks I/O, baseline + orjson)
- **GREEN** : `services/file_utils.py` migré `json` → `orjson` (read/write atomique)
- **GREEN** : `services/memory.py` migré `json.load` → `file_utils.read_json`
- **GREEN** : `pyproject.toml` + `requirements.txt` → `orjson>=3.11` ajouté
- **FEATURE** : `write_json_batch()` dans `file_utils.py` + tests
- **Résultat** : large writes **4x plus rapides P50** (58.9ms → 14.4ms), lectures **1.8x**

### 8.5 ✅ Rapport final — DONE (26/07/2026)
`rapport_perf.md` créé avec comparaison stdlib/orjson et métriques P50/P95/P99.

**→ Phase 8 complétée** : score de performance estimé 85 → 90+ (objectif atteint).

---

## 🎨 Phase 9 — Polish UX (confirmée, avec une nuance importante sur 9.1)

### 9.1 ✅ Focus Trap complet (modals) — CLOSED (26/07/2026)
`tests/test_modal_accessibility.py` existe et **passe**, mais son assertion est trop faible (`querySelectorAll` apparaît n'importe où dans `app.js`, donc le test est vert sans que la fonctionnalité existe). Vérification directe : **aucun handler `Tab`/`shiftKey` de cycle de focus n'existe** dans `app.js` — seule la fermeture par `Escape` est implémentée (MT-FE-2).

#### Micro-tâches exécutées (26/07/2026)
| # | Micro-tâche | Statut |
|---|-------------|--------|
| 9.1.1 | **RED** : renforcer le test (vérifier vrais cycles Tab/Shift+Tab, `preventDefault`, `firstFocusable`/`lastFocusable`) | ✅ |
| 9.1.2 | **GREEN** : implémenter `trapTabKey()` + stockage `_lastFocused` + restauration dans `closeBrowser()` | ✅ |
| 9.1.3 | **Focus initial** : `firstFocusable.focus()` dans `openBrowser()` | ✅ |
| 9.1.4 | **Refactor** : `getFocusableElements()` + `trapTabKey()` utilitaires réutilisables | ✅ |
| 9.1.5 | **Vérification** : 6 tests modal + 45 tests connexes passés, 0 failed | ✅ |
- **Fichiers modifiés** : `tests/test_modal_accessibility.py`, `static/assets/js/app.js`
- **Commit** : `feat(ui): focus trap réel sur modale File Browser + durcit le test`

### 9.2 ✅ Skeleton Loaders — Skills & Analytics — CLOSED (26/07/2026)
`injectSkeletons()` appelée dans `refreshAgents()` et `refreshTools()`, mais **pas** dans `refreshSkills()` ni `refreshAnalytics()`. Le test vérifiait `>= 3` — trop faible.
- **RED** : seuil `>= 3` → `>= 5` dans `tests/test_skeleton_loaders.py` (assertion `assert nb >= 5`)
- **GREEN** : injection dans `static/assets/js/app.js`
  - `refreshSkills()` l.493 : `injectSkeletons(grid, 7)` (7 skills dans `config/skills.json`)
  - `refreshAnalytics()` l.799 : `injectSkeletons(document.getElementById('analytics-kpis'), 8)` (8 KPI cards)
- **Preuve** : 73 tests passés (skeleton + modal + CSP + security + chunker + file_utils + cache + router + portability + no_silent_except), 0 failed

### 9.3 ✅ Toasts animés (feedback mémoire) — CLOSED (25/07/2026)
Le système `toast()` existe et est utilisé ailleurs (assignation de modèle, erreurs réseau), mais **aucun appel `toast()` après les clics 👍/👎** (`fetch('/api/feedback', ...)` et `/api/feedback/implicit` ne déclenchent rien visuellement).
- **RED** : `tests/test_feedback_toast.py` (créé) — 2 tests vérifient la présence de `toast(` dans `sendFeedback()` et `sendImplicit()`
- **GREEN** : `toast('Merci pour votre retour 👍', 'success')` dans `sendFeedback()` (signal=1), `toast('Noté, on fera mieux 👎', 'info')` (signal=-1), `toast('Réponse copiée 📋', 'success')` dans `sendImplicit()` (type='copy')
- **Preuve** : 34 tests passés (2 nouveaux + 32 existants), 0 failed

### 9.4 ✅ Dark mode toggle — COMPLÉTÉ (26/07/2026)
`tests/test_dark_mode.py` créé (3 tests) + `:root[data-theme="light"]` dans `style.css` + `#theme-toggle` dans sidebar + `initThemeToggle()`/`getTheme()`/`setTheme()`/`toggleTheme()` dans `app.js`. Persistance via `localStorage('jarvis_theme')`. Transition CSS douce. Preuve : 819 passed / 0 failed / 40 skipped / 1 xfailed (3 nouveaux tests).

---

## 📝 Phase 10 — Docs & Maintenance

### 10.1 🟡 Mise à jour ROADMAP.md — partiellement fait
`docs/dev-history/ROADMAP.md` reflète déjà un état "tout ✅" pour son propre périmètre (UI/Portabilité), mais ne mentionne pas les Phases 7-9 de ce backlog. À compléter plutôt qu'à recréer.

### 10.2 🔴 CHANGELOG.md — à mettre à jour
Le fichier existe et va jusqu'à la v5.2 (juillet 2026) mais ne documente pas les commits récents (sandbox sécurité 7.1-7.6, nettoyage `.opencode/`). Toujours pertinent.

### 10.3 ✅ Header `X-XSS-Protection` — déjà résolu en pratique, nettoyage doc restant
Vérification faite dans `controllers/middlewares.py` : le header **n'est jamais envoyé** (seuls `X-Content-Type-Options` et `X-Frame-Options` le sont). La mention "à faire" en tête de fichier (commentaire de dette technique) est donc obsolète.
- **Reste à faire** : supprimer le commentaire de dette périmé + ajouter `tests/test_security_headers.py` en garde-fou anti-régression (aucun test ne protège ce comportement aujourd'hui)
- **Commit** : `docs(security): nettoie le commentaire de dette X-XSS-Protection obsolète + garde-fou test`

### 10.4 ✅ `os.system("cls")` → `subprocess.run` — DÉJÀ FAIT (backlog disait 🔴)
Aucune occurrence d'`os.system` dans `services/launcher.py`. Rien à coder.

### 10.5 ✅ Suppression stubs legacy — CLOSED (25/07/2026)
`_check_ollama` (dupliqué dans `context.py` ET `router.py` via `InferenceService.ping()`) et `_sync_module_globals` (no-op total, corps = `pass`) étaient du code mort : la vraie route `/api/status` utilise `router._build_status` (→ `context.inference.ping()` direct) et `controllers/status.py` a sa propre implémentation réelle (`OllamaAdapter._check_endpoint` sur le port portable), inchangée.
- **RED/GREEN** : suppression des 2 stubs + réécriture de `tests/test_wave_a.py` (A4) pour tester le vrai `controllers.status._check_ollama()` (mock sur `OllamaAdapter._check_endpoint`) au lieu du stub mort ; mise à jour de `test_context_refactor.py`, `test_api.py`, `test_endpoints_async.py`, `test_profiling.py` (retrait des patches de compatibilité devenus inutiles)
- **Preuve** : suite complète 805 passed / 0 failed / 40 skipped / 1 xfailed (inchangé, aucune régression)
- **Commit** : `refactor: supprime les stubs legacy _check_ollama/_sync_module_globals (code mort)` (`4b00bac`)
- Fichiers modifiés : `controllers/context.py`, `controllers/router.py`, `tests/test_wave_a.py`, `tests/test_context_refactor.py`, `tests/test_api.py`, `tests/test_endpoints_async.py`, `tests/test_profiling.py`

---

## 📊 Ordre Recommandé (mis à jour selon l'état réel)

| Priorité | Tâche | Effort estimé | Impact |
|----------|-------|----------------|--------|
| 🟢 1 | ✅ **9.4 Dark mode toggle** — FAIT | 2h | UX confort |
| 🔵 2 | 10.1 / 10.2 / 10.3 Docs (ROADMAP, CHANGELOG, nettoyage commentaire) | 1-2h | Doc |

**Déjà fait, rien à planifier** : tout Phase 8 (orjson + profiling + rapport), Phase 7, Phase 9.1-9.4, 10.4, 10.5.

---

## ✅ Règles de Validation (rappel, inchangées)

1. UNE micro-tâche = UN fichier = UN cycle RED/GREEN
2. Preuve verte collée AVANT de cocher [x]
3. Commit = point de retour sûr immédiat après le GREEN
4. Ne pas mélanger chantier Sécurité et chantier Perf
5. Après tout collage de fichier Python : vider `__pycache__`
6. Tests TDD : écrire le test AVANT le code
7. Tout correctif touchant aux chemins/fichiers : valider sur Windows ET Linux

---

## 🎯 Prochaine Action

### Session du 25/07/2026 — CLOSED
0.1, 7.4 et 10.5 traitées et committées (`7dd6401`, `05265fb`, `4b00bac`).
```bash
git am 0001-docs-aligne-README-suite-au-retrait-de-.opencode.patch
git am 0002-fix-security-masque-le-d-tail-d-exception-brut-dans-.patch
git am 0003-refactor-supprime-les-stubs-legacy-_check_ollama-_sy.patch
```

### Session du 26/07/2026 — 9.2 ✅
- **Tâche** : 9.2 Skeleton loaders Skills/Analytics
- **RED** : seuil `>= 3` → `>= 5` dans `tests/test_skeleton_loaders.py`
- **GREEN** : `injectSkeletons(grid, 7)` dans `refreshSkills()` (app.js:493) + `injectSkeletons(kpisGrid, 8)` dans `refreshAnalytics()` (app.js:799)
- **Preuve** : 73 tests passés, 0 failed

### Session du 25/07/2026 — 9.3 ✅
- **Tâche** : 9.3 Toasts animés feedback mémoire
- **RED** : `tests/test_feedback_toast.py` (créé) — présence de `toast(` dans `sendFeedback()` et `sendImplicit()`
- **GREEN** : `toast()` après fetch dans `sendFeedback()` (👍/👎) et `sendImplicit()` (📋 copy)
- **Preuve** : 34 tests passés (2 nouveaux + 32 existants), 0 failed

### Session du 26/07/2026 — 9.1 ✅ focus trap
- **Tâche** : 9.1 Focus trap réel sur modales
- **9.1.1 RED** : test renforcé (6 tests, 0 implémentation → 3 failed)
- **9.1.2–9.1.4 GREEN** : `trapTabKey()`, `getFocusableElements()`, focus initial, store/restore `_lastFocused`
- **9.1.5 Vérification** : 6/6 test modal accessibilité + 45 tests connexes passés

### Session du 26/07/2026 — Phase 8 complète ✅
- **Tâche** : 8.4 I/O `orjson` + batch writes
- **RED** : `tests/test_io_perf.py` créé (4 tests benchmark baseline)
- **GREEN** : `services/file_utils.py` → `orjson` (read/write atomique + `write_json_batch`)
- **GREEN** : `services/memory.py` → `file_utils.read_json` (via orjson)
- **GREEN** : `pyproject.toml` + `requirements.txt` → `orjson>=3.11`
- **Résultat** : large writes **4x P50** (58.9→14.4ms), lectures **1.8x**
- **8.0** : `scripts/profile_app.py` + `scripts/bench_runner.py` créés
- **8.5** : `rapport_perf.md` rédigé avec comparaison stdlib/orjson
- **Vérification** : 186 tests passés (file_utils + memory + io_perf + router + wave_a + log + metrics + analytics + facts + vector + chunker + sanitize + ratelimit + security), 0 failed
- **Prochaine tâche** : 9.4 Dark mode (ou docs 10.1-10.3)

### Session du 26/07/2026 — 9.4 ✅ Dark mode toggle
- **Tâche** : 9.4 Dark mode toggle
- **9.4.1 RED** : `tests/test_dark_mode.py` (créé) — 3 tests : bouton, CSS light, JS persistence
- **9.4.2 GREEN CSS** : `:root[data-theme="light"]` + variables inversées + transition douce
- **9.4.3 GREEN HTML** : `#theme-toggle` dans sidebar-header avec `aria-pressed`
- **9.4.4 GREEN JS** : `initThemeToggle()`, `getTheme()`, `setTheme()`, `toggleTheme()` + localStorage `jarvis_theme`
- **Preuve** : 819 passed / 0 failed / 40 skipped / 1 xfailed (3 nouveaux)
- **Fichiers modifiés** : `static/assets/css/style.css`, `static/index.html`, `static/assets/js/app.js`, `tests/test_dark_mode.py`
- **Prochaine tâche** : 10.1 / 10.2 / 10.3 Docs
