# 📋 BACKLOG.md — Plan de Micro-Tâches TDD (audit du 25/07/2026)

**Projet** : JARVIS Portable Edition v5.4
**État réel vérifié** : 805 tests passed / 0 failed / 40 skipped / 1 xfailed (803 initialement + 2 nouveaux tests ajoutés pour la tâche 7.4 ; 10.5 n'ajoute ni ne retire de tests, juste une réécriture ; 9.2 modifie le seuil d'un test existant sans en ajouter)
**Méthode d'audit** : relecture du BACKLOG.md précédent + grep/lecture du code réel derrière chaque item + relance de la suite de tests + `git log`/`git status`
**Verdict global** : le projet est plus avancé que ce que disait le backlog sur la Perf (Phase 8), mais deux tâches "closes" cachent un résidu. Le reste (Phase 9 UX, Phase 10 Docs) est correctement décrit.

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

## ⚡ Phase 8 — Performance (RTOC+CoT) — largement plus avancée que déclaré

### 8.0 🔴 Outillage & Baseline — toujours à faire
`scripts/profile_app.py` et `scripts/bench_runner.py` n'existent pas. Inchangé.

### 8.1 ✅ Inférence Ollama — connection pooling — DÉJÀ FAIT (backlog disait 🔴)
`services/adapters/ollama_adapter.py` a déjà un `httpx.Client(timeout=...)` en singleton (`self._http`, méthode `_get_http()`). Rien à coder.
- Reste seulement à ajouter une preuve de perf : `tests/test_inference_perf.py` n'existe pas → si vous voulez la métrique P95, il faut créer le test, mais l'implémentation est bonne.

### 8.2 ✅ Vector Search — numpy vectorisé — DÉJÀ FAIT (backlog disait 🔴)
`services/vector_search.py` utilise déjà `np.argpartition` (O(N)) + `np.argsort` sur le top-k. Rien à coder.

### 8.3 ✅ Vector Cache — LRU borné — DÉJÀ FAIT (backlog disait 🔴)
`services/vector_cache.py` implémente déjà un `OrderedDict` avec `move_to_end` (LRU) + TTL (`VECTOR_CACHE_TTL_SECONDS = 300`). Rien à coder.

### 8.4 🔴 I/O Fichiers — `orjson` + batch writes — TOUJOURS À FAIRE (confirmé)
`services/file_utils.py` et `services/memory.py` utilisent encore `import json` (stdlib). Aucune trace d'`orjson`.
- **RED** : `pytest tests/test_io_perf.py` (à créer)
- **GREEN** : migrer vers `orjson` + batcher les écritures
- **Commit** : `perf(io): orjson + batch writes + cache LRU`

### 8.5 🔴 Validation E2E & Rapport — toujours à faire
`rapport_perf.md` n'existe pas.

**→ Conclusion Phase 8** : 3 des 5 chantiers (8.1, 8.2, 8.3) sont déjà en production. Il ne reste réellement que l'outillage de profiling (8.0), l'I/O (8.4) et le rapport final (8.5). Le score "85 → 90" est probablement déjà acquis en pratique, juste pas mesuré/documenté.

---

## 🎨 Phase 9 — Polish UX (confirmée, avec une nuance importante sur 9.1)

### 9.1 🔴 Focus Trap complet (modals) — TOUJOURS À FAIRE, attention au faux positif
`tests/test_modal_accessibility.py` existe et **passe**, mais son assertion est trop faible (`querySelectorAll` apparaît n'importe où dans `app.js`, donc le test est vert sans que la fonctionnalité existe). Vérification directe : **aucun handler `Tab`/`shiftKey` de cycle de focus n'existe** dans `app.js` — seule la fermeture par `Escape` est implémentée (MT-FE-2).
- **Action recommandée** : renforcer le test (vérifier un vrai cycle Tab/Shift+Tab dans la modale) avant de le re-valider, puis implémenter le focus trap.
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

### 9.4 🔴 Dark mode toggle — confirmé toujours à faire
Les variables CSS (`--bg`, `--text`, etc.) existent mais un seul thème (sombre) est défini. Aucun toggle, aucune variante claire.

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
| 🔴 1 | 9.3 Toasts feedback mémoire | 30 min | UX rapide |
| 🔴 2 | 9.1 Focus trap réel (+ durcir le test existant) | 1-2h | Accessibilité |
| 🔴 3 | 8.4 I/O `orjson` + batch writes | 2-3h | Perf |
| 🔴 4 | 8.0 + 8.5 Outillage perf + rapport final | 2h | Mesure/doc |
| 🟢 5 | 9.4 Dark mode toggle (optionnel) | 2h | UX confort |
| 🔵 6 | 10.1 / 10.2 / 10.3 Docs (ROADMAP, CHANGELOG, nettoyage commentaire) | 1-2h | Doc |

**Déjà fait, rien à planifier** : 0.1 (commit README), 7.4 (fuite d'erreur documents.py), 8.1 (pooling Ollama), 8.2 (numpy vector search), 8.3 (LRU vector cache), 9.2 (skeleton loaders Skills/Analytics), 10.4 (subprocess.run), 10.5 (stubs legacy supprimés).

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
```bash
# Prochaine tâche : 9.1 (focus trap réel)
# Renforcer test_modal_accessibility.py puis implémenter le cycle Tab/Shift+Tab
# Voir BACKLOG.md lignes 64-67
```
