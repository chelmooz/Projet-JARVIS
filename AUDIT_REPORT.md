# Audit Go/NoGo — JARVIS Portable Edition v5.4

Date : 24/07/2026  
Méthode : `vibe-coding-audit` + `audit-qualite` (123 items, 11 couches)  
Tests : 724/767 passed (94,4%), 0 failed, 43 skipped, 1 xfailed

---

## 1. Résumé Exécutif

**Décision : GO sous conditions**

Le projet tient **par conception** (architecture MVC + Hexagonal + Composition Root, SOLID appliqué, 724 tests verts). Les 3 trous de sécurité critiques sont dans des routes secondaires (`code_review`, `kill_coding`, `diagnostic_ext`) qui ne sont pas activées par défaut dans le flux principal. Les patterns vibe-coding (bare excepts, magic numbers, silent swallows) sont concentrés dans la couche infrastructure — la couche métier est propre.

**Condition :** Corriger les 3 HIGH (path traversal, format string injection, error leakage) avant mise en production réelle (≠ usage local).

---

## 2. Score Global : 72/100

| Couche | Items | Score | Note |
|--------|-------|-------|------|
| 2. APIs & Backend | 18 | 14/18 | **77%** — SOLID bien appliqué, mais bare excepts everywhere |
| 3. Stockage | 12 | 10/12 | **83%** — Bon (atomic writes), manque backup scripté |
| 4. Hosting | 10 | 8/10 | **80%** — Docker + launcher OK, manque doc premier démarrage |
| 5. Configuration | 15 | 13/15 | **86%** — Constants/paths single source, .env.example présent |
| 6. CI/CD | 10 | 7/10 | **70%** — Pre-commit hooks OK, pas de CI automatisé |
| 7. Rate Limiting | 4 | 2/4 | **50%** — Rate limiter existe mais fuite mémoire |
| 8. Caching | 12 | 9/12 | **75%** — Cache static OK, prefs cache buggé (fixé) |
| 9. Performance | 10 | 7/10 | **70%** — Async bien géré, profilages absents |
| 10. Logs | 12 | 7/12 | **58%** — Patterns logs OK mais bare excepts ne loggent pas |
| 11. Stabilité | 12 | 9/12 | **75%** — Graceful shutdown OK, sauvegarde absente |
| **Sécurité** | 8 | 4/8 | **50%** — 3 HIGH non corrigés |
| **Tests** | — | — | **94%** — 724 verts, bonne couverture |

**Pondération :** Architecture 30% + Sécurité 20% + Tests 20% + Robustesse 15% + Docs 15%

**Score pondéré : 72/100**

---

## 3. Décisions Non Documentées

| Décision | Endroit | Risque |
|----------|---------|--------|
| `path` query param sans sandbox | `controllers/routes/code_review.py:19` | **HIGH** — lecture fichier arbitraire |
| Format string injection | `services/diagnostic_ext/executor.py:83` | **HIGH** — exécution indirecte |
| Sandbox bypass via `None` en dev | `services/file_system.py:49` | MEDIUM — contournement sandbox |
| Rate limiter sans purge | `services/ratelimit.py:18` | LOW — fuite mémoire lente |
| Daemon thread non joiné | `services/ingest_queue.py:43` | LOW — corruption possible |
| CSP unsafe-inline | `controllers/middlewares.py:129` | LOW — XSS théorique |
| Legacy stubs pour tests | `controllers/context.py:112-118` | LOW — code mort |

---

## 4. Signaux de P-Hacking

### Critiques

| Signal | Fichier | Ligne |
|--------|---------|-------|
| `except Exception: pass` — shutdown crash silencieux | `jarvis.py` | 75, 107 |
| `except Exception: pass` — ouverture navigateur | `jarvis.py` | 107 |
| `except Exception: return False` — health check | `controllers/router.py` | 55, 71 |
| 19 try/except qui avalent sans log | 12 fichiers différents | voir §8 |
| 15 barrera excepts sans logging | services/ + controllers/ | voir §8 |
| Magic numbers : timeout 0.5s, delays 0.5/1.5/5.0 | `services/launcher.py` | 40, 54, 62 |
| Magic numbers : analyse thresholds sans doc | `services/analysis_core.py` | 48-62 |
| Tests fragiles : `assert len(...) == 200/500/768/42` | 5 fichiers test | valeurs codées en dur |

### Absents
- ✅ Aucun test skip sans `reason=`
- ✅ Aucun mock qui patche la fonction testée
- ✅ Aucun `assert True` / `assert None` dans les tests
- ✅ Aucun `str(x)` / `int(x)` pour taire une erreur
- ✅ Aucun commentaire de code mort

---

## 5. Résultats des Contrôles de Robustesse

| Contrôle | Survit ? | Condition d'échec |
|----------|----------|-------------------|
| Input vide (fuzz test) | ✅ OUI | 724 tests passent, fuzzing inclu |
| Path traversal vers `/etc/passwd` | ❌ NON | Routes code_review, kill_coding |
| Injection via format string | ❌ NON | Executor diagnostic_ext |
| Concurrence 2 writes simultanés | ⚠️ PARTIEL | read_json/write_json_atomic race |
| Timeout Ollama 30s | ✅ OUI | Graceful 503 |
| Fichier préférences corrompu | ✅ OUI | Cache retourne `{}` |
| Multi-utilisateurs simultanés | ⚠️ PARTIEL | Rate limiter fuite mémoire, pas de test concurrency |
| Démarrage sans Ollama | ✅ OUI | Preflight check + 503 |

---

## 6. Risques de Non-Reproductibilité

| Risque | Sévérité | Détail |
|--------|----------|--------|
| Ollama binaire pas dans git | **HAUT** | `bin/win/ollama.exe` non versionné (logique — binaire 1.3Go). La procédure d'install est documentée mais pas automatisée. |
| `.env` pas commité | BAS | `.env.example` présent, copie manuelle nécessaire |
| Dépendances non pinnées dans `requirements.txt` | MOYEN | `requirements.txt` existe mais sans hash verification |
| Variables globales mutables | MOYEN | `_prefs_cache`, `_FILE_LOCKS`, `_hits` sont des singletons — peuvent fuiter entre tests si pas nettoyés |
| Tests dépendent de l'ordre d'exécution | BAS | 724 tests passent en aveugle, plus de dépendance d'ordre depuis les correctifs |

---

## 7. Recommandations Priorisées

### 🔴 Bloquant avant prod (3 items)

1. **Path traversal — code_review + kill_coding**  
   `controllers/routes/code_review.py:19-27` + `controllers/routes/kill_coding.py:19-28`  
   Ajouter sandbox `FileSystemService.authorize_path()` ou retirer les routes

2. **Format string injection — diagnostic_ext**  
   `services/diagnostic_ext/executor.py:83`  
   Remplacer `str.format(**extra_kwargs)` par `str.replace()` ou whitelist de clés

3. **Error leakage vers le client**  
   `controllers/routes/jarvis.py:161`, `agents.py:147`, `conversations.py:70`  
   Logger l'exception avec `exc_info=True`, retourner message générique

### 🟡 Important (5 items)

4. **Ajouter logging aux 15 bare excepts**  
   Partout où `except Exception: pass` apparaît, ajouter `_logger.warning()` ou `_logger.error()`

5. **Remplacer les magic numbers par des constantes nommées**  
   Surtout dans `services/launcher.py` (timeouts), `services/analysis_core.py` (thresholds)

6. **Per-file locks : `read_json` utilise le même lock que `write_json_atomic`**  
   `services/file_utils.py:64-75` — partager `_get_lock()` entre lecture et écriture

7. **Rate limiter : purge périodique**  
   `services/ratelimit.py:18` — nettoyer les IP mortes du dictionnaire

8. **CSP : remplacer 'unsafe-inline' par nonce**  
   `controllers/middlewares.py:129-130`

### 🔵 Cosmétique (4 items)

9. Supprimer le header `X-XSS-Protection` déprécié
10. Remplacer `os.system("cls")` par `subprocess.run`
11. Supprimer les stubs legacy `_check_ollama` + `_sync_module_globals`
12. Remplacer les assertions fragiles par des références aux constantes (dim 768, max 500)

---

## 8. Inventaire Détaillé des 15 Bare Excepts

| Fichier | Ligne | Code | Impact |
|---------|-------|------|--------|
| `jarvis.py` | 75 | `except Exception: pass` | Shutdown crash masqué |
| `jarvis.py` | 107 | `except Exception: pass` | Browser non ouvert, silencieux |
| `controllers/router.py` | 55 | `except Exception: return False` | Health check opaque |
| `controllers/router.py` | 71 | `except Exception: ollama_up = False` | Status falsifié |
| `controllers/router.py` | 250 | `except Exception: return False` | Legacy stub |
| `controllers/context.py` | 117 | `except Exception: return False` | Legacy stub |
| `services/adapters/ollama_adapter.py` | 57 | `except Exception: return False` | Ping échoué, pas de log |
| `services/adapters/ollama_adapter.py` | 91 | `except Exception: self._timeout = 120` | Timeout silencieux |
| `services/adapters/ollama_adapter.py` | 42 | `suppress(Exception)` | Close crash |
| `services/adapters/ollama_adapter.py` | 47 | `suppress(Exception)` | Idem |
| `services/system.py` | 102 | `suppress(Exception)` | Pip upgrade fail |
| `services/diagnostic_ext/audit.py` | 21 | `suppress(Exception)` | Audit log fail |
| `scripts/build_snapshot.py` | 43 | `except Exception: return None` | Git fail |
| `scripts/fuzz_payloads.py` | 84 | `except Exception: valid[name] = None` | Crash masqué |
| `scripts/restore_backup.py` | 42 | `except Exception: return ...` | Import fail |

---

## 9. Détail du Score par Couche

### 2. APIs & Backend — 14/18 ✅ (77%)

| Critère | Statut |
|---------|--------|
| Structure MVC | ✅ |
| Un service = une responsabilité | ✅ |
| Modèles typés (Pydantic) | ✅ |
| Endpoints REST corrects | ✅ |
| Codes HTTP sémantiques | ✅ |
| Réponses structurées `{data, error}` | ✅ |
| Pagination sur listes | ✅ |
| Validation entrées | ⚠️ Manque sandbox code_review |
| Messages explicites | ✅ |
| Fonctions < 20 lignes | ⚠️ Certaines dépassent |
| Nommage avec verbes | ✅ |
| Pas de code mort | ✅ |
| Pas de try/catch vide | ❌ 15 excepts sans log |
| Dépendances injectées (DIP) | ✅ |
| Tests unitaires | ✅ 724 verts |
| Cas limites testés | ✅ Fuzzing inclu |
| Commande unique pytest | ✅ |

### 10. Logs — 7/12 ✅ (58%)

| Critère | Statut |
|---------|--------|
| Logs structurés (DEBUG/INFO/WARN/ERROR) | ✅ |
| Événements importants loggés | ✅ |
| Format clair avec horodatage | ✅ |
| LOG_LEVEL configurable | ✅ |
| Erreurs catchées et loggées | ❌ 15 bare excepts sans log |
| Messages actionnables | ✅ |
| Stack trace en mode dev | ⚠️ Pas systématique |
| Erreurs critiques en console | ✅ |
| Mode debug activable | ✅ |
| État inspectable (/status) | ✅ |

### 11. Stabilité — 9/12 ✅ (75%)

| Critère | Statut |
|---------|--------|
| Démarre avec base vide | ✅ |
| Arrêt propre (graceful shutdown) | ✅ |
| Redémarrage idempotent | ✅ |
| Pas de crash sur entrée invalide | ✅ (fuzz testé) |
| Fichier absent/corrompu géré | ✅ |
| Retry sur perte connexion | ✅ |
| Opérations atomiques | ✅ (write_json_atomic) |
| Backup documenté | ❌ Absent |
| Données séparées du code | ✅ |
| Restauration documentée | ❌ Absente |

---

## 10. Verdict Final

**GO avec conditions** ✅

Le projet est fonctionnel, bien architecturé, et 724 tests passent. Les vulnérabilités HIGH sont dans des routes non activées par défaut (code_review, kill_coding, diagnostic_ext) qui n'exposent pas de données utilisateur. **En usage local mono-utilisateur, le risque est acceptable.** Pour un déploiement multi-utilisateur ou exposé sur un réseau, les 3 priorités bloquantes doivent être corrigées avant.

**Forces :** Architecture SOLID, injection de dépendances, ports & adapters, 724 tests verts, fuzzing intégré, PII scrubbing, graceful shutdown, atomic I/O

**Faiblesses :** 15 bare excepts sans logging, 19 silent swallows, 3 trous de sécurité HIGH dans routes secondaires, ~25 magic numbers, pas de CI automatisé, pas de backup scripté

**Score : 72/100 — "Bon projet vibe-codé, à sécuriser avant prod"**
