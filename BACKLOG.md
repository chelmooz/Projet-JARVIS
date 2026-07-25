# 📋 BACKLOG.md — Plan de Micro-Tâches TDD (mise à jour)

**Projet** : JARVIS Portable Edition v5.4
**État** : Phases 1-7.3 + 7.5 complétées ✅ · 803 tests verts sur Linux (0 failed) · ⚠️ 23 failed sur Windows (voir 7.6) · Score audit en progression
**Objectif** : Passer à 90+/100 en corrigeant les HIGH restants (dont 7.4, 7.6) + perf + polish
**Règle d'or** : 1 micro-tâche = 1 fichier = 1 cycle RED/GREEN = 1 commit

---

## ✅ Phase 7 — Sécurité (partiellement close)

### 7.1 ✅ Path traversal — `code_review` (CLOSED)
- Commit : `fix(security): sandbox path traversal dans code_review`
- Fichiers modifiés : `controllers/routes/code_review.py`, `services/file_system.py`, `tests/conftest.py`
- Durcissement cross-platform de `FileSystemService.authorize_path()`

### 7.1.1 ✅ Fix TypeError `authorize_path` (Path vs str) (CLOSED)
- **RED** : `pytest tests/test_file_system.py` → `test_secure_by_default_en_production` : `TypeError: Path.replace() takes 2 positional arguments but 3 were given` (`PROJECT_DIR` est un `Path`, passé tel quel à `authorize_path()` qui appelait `.replace("\\","/")` — collision avec `Path.replace()`, l'API de renommage de fichier)
- **GREEN** : ajout de `path = str(path)` en tête de `authorize_path()` (`services/file_system.py`)
- **Preuve** : `tests/test_file_system.py` 23/23 passed ; suite complète 802 passed / 0 failed / 40 skipped / 1 xfailed (vs 801/1 failed avant)
- **Commit** : `fix(security): caste path en str dans authorize_path (TypeError Path.replace)`
- Fichier modifié : `services/file_system.py`

### 7.2 ✅ Path traversal — `kill_coding` (CLOSED)
- Commit : `fix(security): confirme et teste la sandbox path traversal dans kill_coding`
- Fichier modifié : `tests/test_security_path_traversal.py`
- Les 3 endpoints étaient déjà sécurisés — 15 tests TDD ajoutés comme preuve

### 7.3 ✅ Format string injection — `diagnostic_ext` (CLOSED)
- Commit : `fix(security): élimine format string injection dans executor`
- Fichiers modifiés : `services/diagnostic_ext/executor.py`, `tests/test_security_format_string.py`, `tests/test_diagnostic_ext_executor_tdd.py`
- Substitution en passe unique via `re.sub` + whitelist `allowed_params` + regex stricte

### 7.4 🔴 Error leakage vers le client (À FAIRE)
- **Fichiers** : `controllers/routes/jarvis.py`, `agents.py`, `conversations.py`
- **Problème** : Stack traces exposées au client
- **RED** : `pytest tests/test_security_error_leakage.py` (à créer)
- **GREEN** : Logger avec `exc_info=True`, retourner message générique
- **Commit** : `fix(security): masque les stack traces côté client`

### 7.5 ✅ Logging des bare excepts (CLOSED)
- **Constat** : les 15 excepts listés en AUDIT_REPORT §8 étaient déjà loggés (fix antérieur non reflété dans ce backlog)
- **RED réel** : garde-fou AST (`tests/test_no_silent_except.py::TestNoBareExceptPass`) a détecté 5 `except: pass` silencieux supplémentaires, hors de la liste §8 : `services/analysis_audit.py:327`, `services/launcher.py:54`, `services/vector.py:166`, `services/diagnostics/checks.py:54`, `services/diagnostics/checks.py:155`
- **GREEN** : `_logger.debug(...)` ajouté sur les 5 (logger créé dans `analysis_audit.py`, absent avant) ; le garde-fou AST scanne désormais tout le code de prod en continu (anti-régression)
- **Preuve** : suite complète 803 passed / 0 failed / 40 skipped / 1 xfailed (vs 802 avant, +1 = le nouveau test de garde-fou)
- **Commit** : `fix(security): log les 5 except:pass silencieux restants + garde-fou AST anti-régression`
- Fichiers modifiés : `services/analysis_audit.py`, `services/launcher.py`, `services/vector.py`, `services/diagnostics/checks.py`, `tests/test_no_silent_except.py`

### 7.6 🔴 Régression Windows — `authorize_path` rejette `PROJECT_DIR` lui-même (À FAIRE)
- **Constat** : run pytest complet sur Windows (H:\Projet-JARVIS) après 7.5 → 23 failed / 779 passed (vs 803 passed sur Linux dans le même commit). Non reproduit sous Linux — spécifique au sandbox path Windows.
- **Symptôme** : `FileSystemService.authorize_path()` logue `"Tentative de path traversal bloquée (lecteur Windows)"` et rejette systématiquement, y compris pour `PROJECT_DIR` lui-même (`WindowsPath('H:/Projet-JARVIS')`) et pour des dossiers temp légitimes (`tempfile.mkdtemp()`).
- **Fichiers impactés** : `services/file_system.py` (logique de blocage lecteur Windows, log ligne 79) ; tests rouges : `tests/test_api_files.py` (6), `tests/test_file_system.py` (11), `tests/test_toolbox.py` (5)
- **Cas critique** : `TestFileSystemSecureByDefault::test_secure_by_default_en_production` échoue sur `svc.authorize_path(PROJECT_DIR)` — si le sandbox refuse même son propre dossier projet, aucune route `/api/files/*` n'est utilisable en usage réel sur Windows
- **RED** : déjà rouge sur Windows (voir run ci-dessus) — pas reproductible dans le sandbox Linux de dev, donc écrire un test qui simule explicitement un chemin `H:\...`/drive letter Windows sans dépendre de l'OS hôte
- **GREEN** : identifier pourquoi le durcissement 7.1 ("lecteur Windows") bloque un chemin légitime — probablement une regex/comparaison de lecteur trop stricte introduite lors du hardening cross-platform
- **Commit** : `fix(security): corrige le faux positif path-traversal sur lecteur Windows dans authorize_path`

---

## 🪟 Phase 7-bis — Suivi Windows (issue live)

### État constaté (run réel du 25/07, commit 6a2e4fd)
- 23 failed / 779 passed / 40 skipped / 1 xfailed / 2 warnings sur Windows, vs 803 passed / 0 failed sur Linux (même commit)
- Tous les échecs remontent à la même cause racine (7.6) : `authorize_path()` bloque toute autorisation de dossier sous Windows, y compris légitime
- Priorité : à traiter avant Phase 8 (perf) — un sandbox fichiers cassé sur la plateforme cible principale (Windows) est bloquant pour l'usage réel

## ⚡ Phase 8 — Performance (RTOC+CoT)

### 8.0 🔴 Outillage & Baseline
- **Fichiers** : `scripts/profile_app.py` + `scripts/bench_runner.py`
- **RED** : Profiler l'app mockée → identifier top 3 goulots
- **GREEN** : Scripts de benchmark fonctionnels
- **Commit** : `chore(perf): outillage de profilage`

### 8.1 🔴 Inférence Ollama — connection pooling
- **Fichier** : `services/adapters/ollama_adapter.py`
- **Problème** : Client HTTP recréé à chaque appel
- **RED** : `pytest tests/test_inference_perf.py` → P95 > 50ms
- **GREEN** : `httpx.Client` singleton + timeout adaptatif
- **Commit** : `perf(inference): connection pooling + timeout adaptatif`

### 8.2 🔴 Vector Search — numpy vectorisé
- **Fichier** : `services/vector_search.py`
- **Problème** : Recherche O(N) naïve en Python
- **RED** : `pytest tests/test_vector_perf.py` → P95 > 50ms sur 5k docs
- **GREEN** : `numpy.dot` + `argsort` vectorisé
- **Commit** : `perf(vector): recherche numpy vectorisée`

### 8.3 🔴 Vector Cache — LRU borné
- **Fichier** : `services/vector_cache.py`
- **Problème** : Pas de cache pour les embeddings fréquents
- **RED** : `pytest tests/test_vector_cache.py` → hit rate < 70%
- **GREEN** : Cache LRU avec `MAX_VECTOR_CACHE=32` + TTL
- **Commit** : `perf(vector): cache LRU borné`

### 8.4 🔴 I/O Fichiers — `orjson` + batch writes
- **Fichiers** : `services/file_utils.py`, `services/memory.py`
- **Problème** : `json` stdlib lent, writes non batchés
- **RED** : `pytest tests/test_io_perf.py` → P95 > 20ms
- **GREEN** : `orjson` + batch writes + cache mémoire
- **Commit** : `perf(io): orjson + batch writes + cache LRU`

### 8.5 🔴 Validation E2E & Rapport
- **Fichier** : `rapport_perf.md`
- **RED** : Benchmark E2E sur 10 conversations complètes
- **GREEN** : P95 < cible sur tous les endpoints
- **Commit** : `docs(perf): rapport de performance final`

---

## 🎨 Phase 9 — Polish UX

### 9.1 🔴 Focus Trap complet (modals)
- **Fichier** : `static/assets/js/app.js`
- **Problème** : La tabulation peut sortir de la modale File Browser
- **RED** : `pytest tests/test_modal_accessibility.py` → ajouter test focus trap
- **GREEN** : Implémenter focus trap basique (cycle Tab/Shift+Tab)
- **Commit** : `feat(ui): focus trap sur modale File Browser`

### 9.2 🔴 Skeleton Loaders — Skills & Analytics
- **Fichier** : `static/assets/js/app.js`
- **Problème** : Onglets Skills/Analytics sans feedback visuel
- **RED** : `pytest tests/test_skeleton_loaders.py` → étendre aux 2 onglets
- **GREEN** : Appeler `injectSkeletons()` dans `refreshSkills()` et `refreshAnalytics()`
- **Commit** : `feat(ui): skeleton loaders sur Skills & Analytics`

### 9.3 🔴 Toasts animés (feedback mémoire)
- **Fichiers** : `static/assets/js/app.js` + `static/assets/css/style.css`
- **Problème** : Feedback 👍/👎 peu visible
- **RED** : `pytest tests/test_toast_feedback.py`
- **GREEN** : Toast de confirmation après clic feedback
- **Commit** : `feat(ui): toast de confirmation feedback mémoire`

### 9.4 🔴 Dark mode toggle (optionnel)
- **Fichiers** : `static/assets/js/app.js` + `static/assets/css/style.css`
- **Problème** : Pas de mode clair
- **RED** : `pytest tests/test_theme_toggle.py`
- **GREEN** : Bouton toggle + variables CSS `--bg`, `--text`
- **Commit** : `feat(ui): toggle dark/light mode`

---

## 📝 Phase 10 — Docs & Maintenance

### 10.1 🔴 Mise à jour ROADMAP.md
- **Action** : Cocher MT-FE-2, MT-FE-3, MT-6.1, MT-6.2 + Phases 7.1/7.2/7.3
- **Commit** : `docs: met à jour ROADMAP.md (Phases 6-9)`

### 10.2 🔴 CHANGELOG.md
- **Action** : Documenter les commits récents (CSP, frontend, portabilité, sécurité sandbox)
- **Commit** : `docs: CHANGELOG v5.4.1`

### 10.3 🔴 Suppression header `X-XSS-Protection` déprécié
- **Fichier** : `controllers/middlewares.py`
- **RED** : `pytest tests/test_security_headers.py`
- **GREEN** : Retirer le header
- **Commit** : `fix(security): retire header X-XSS-Protection déprécié`

### 10.4 🔴 Remplacer `os.system("cls")` par `subprocess.run`
- **Fichier** : `services/launcher.py`
- **RED** : `pytest tests/test_launcher_subprocess.py`
- **GREEN** : Utiliser `subprocess.run`
- **Commit** : `fix(launcher): remplace os.system par subprocess.run`

### 10.5 🔴 Suppression stubs legacy
- **Fichiers** : `controllers/context.py`, `controllers/router.py`
- **RED** : `pytest tests/test_no_legacy_stubs.py`
- **GREEN** : Supprimer les fonctions `_check_ollama` + `_sync_module_globals`
- **Commit** : `refactor: supprime les stubs legacy`

---

## 📊 Ordre Recommandé (mise à jour)

| Priorité | Phase | Durée estimée | Impact | État |
|----------|-------|---------------|--------|------|
| ✅ 1 | Phase 7.1-7.3 (+ fix 7.1.1) (Sécurité sandbox) | 3h | Score audit 72 → 80 | **CLOSED** |
| 🔴 2 | Phase 7.4-7.5 (Sécurité résiduelle) | 2-3h | Score audit 80 → 85 | À faire |
| 🟡 3 | Phase 8 (Performance) | 6-8h | UX + score audit 85 → 90 | À faire |
| 🟢 4 | Phase 9 (Polish UX) | 2-3h | Score audit 90 → 92 | À faire |
| 🔵 5 | Phase 10 (Docs) | 1-2h | Score audit 92 → 95 | À faire |

---

## ✅ Règles de Validation (rappel)

1. **UNE micro-tâche = UN fichier = UN cycle RED/GREEN**
2. **Preuve verte collée AVANT de cocher [x]**
3. **Commit = point de retour sûr immédiat après le GREEN**
4. **Ne PAS mélanger chantier Sécurité et chantier Perf**
5. **Après tout collage de fichier Python : vider `__pycache__`**
6. **Tests TDD : écrire le test AVANT le code (RED → GREEN → REFACTOR)**
7. **Tout correctif touchant aux chemins/fichiers : valider sur Windows ET Linux (cross-platform)**

---

## 🎯 Prochaine Action au Réveil

Vérification déjà faite cette session : `git status` (RAS, seul bruit CRLF/LF sur fichiers non liés), `git log`, `pytest tests/ -q` → 802 passed / 0 failed / 40 skipped / 1 xfailed après le fix 7.1.1.

```bash
# Démarrer Phase 7.4 (error leakage)
# Ouvrir controllers/routes/jarvis.py
# Écrire le test RED dans tests/test_security_error_leakage.py
```

---

**Bon repos !** 🌙
Les 3 micro-tâches de sécurité les plus critiques (sandbox path traversal + format string injection) sont closes et testées, plus un bug réel trouvé et corrigé en cours de route (7.1.1). La suite (7.4/7.5) est plus légère — ce sont des nettoyages de stack traces et de bare excepts. Reprends tranquillement à la Phase 7.4. 💪
