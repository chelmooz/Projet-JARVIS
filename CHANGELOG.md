# Changelog — JARVIS Portable Edition

## [5.4] — 2026-07-21

### Audit DevOps Qwen 3.8 — Corrections critiques
- **D1** : Unification de la gestion des dépendances — `requirements.txt` supprimé, installation directe depuis `pyproject.toml`
- **D2** : Suppression du contournement PEP 668 (`--break-system-packages`) dans `scripts/install.py`
- **D3** : Nettoyage des launchers (auto-install `pip` supprimée, erreurs explicites)
- **D4** : Correction de la race condition sur les ports — `time.sleep()` remplacé par `wait_for_port_free()` avec vérification active
- **D5** : Téléchargement Ollama déterministe — version `0.30.10` épinglée au lieu de `latest`
- **D6** : Vérification d'intégrité SHA256 ajoutée pour les binaires Ollama
- **D8** : Suppression de `install_openwebui()` (code mort)
- **D9** : Simplification de `ensure_venv()` dans `services/system.py`
- **D10** : Augmentation du timeout de téléchargement à 600s (`LAUNCHER_DOWNLOAD_TIMEOUT`)

### Refactoring
- Extraction de `wait_for_port_free()` dans `services/launcher.py`
- Centralisation de la version Ollama dans `config/constants.py` (`OLLAMA_VERSION`)
- Nettoyage des fichiers temporaires et caches

### Frontend — Corrections bugs & accessibilité (Design Senior DevOps)
- **HTML** : `initial-scale=1.0` → `1` (validation W3C) ; meta `description` + Open Graph ajoutées
- **Accessibilité** : `aria-label`, `role`, `aria-live` sur tous les boutons, nav, status et modales
- **Résilience** : `<noscript>` banner + `onerror` sur `app.js` + `defer` sur tous les scripts
- **Sécurité** : `accept="image/*"` → types MIME explicites (`image/png,jpeg,webp,gif`)
- **CSS** : style `.noscript-banner` ajouté (erreur JS visible à l'utilisateur)

## [5.3] — 2026-07-11

### Mémoire auto-améliorante (Étapes 0→6)
- **Étape 0** : `POST /api/vectorize/conversations` non-destructif et idempotent
  (`mark_indexed`/`list_unindexed` remplacent la suppression des conversations
  après indexation).
- **Étape 1** : auto-ingest asynchrone (`IngestQueue`, thread daemon, démarré
  uniquement en `lifespan`) + IDs uuid12 sur chaque message (`backfill_message_ids`).
- **Étape 2** : `index_message()` — provenance (conv_id/msg_id/role) + poids initial.
- **Étape 3** : signal qualité — `adjust_weight()` (feedback explicite ±, clamp
  `[WEIGHT_MIN, WEIGHT_MAX]`, co-contributeur message précédent ×0.5) + feedback
  implicite. Endpoints `POST /api/feedback` et `/api/feedback/implicit`.
- **Étape 4** : recherche pondérée `score = similarité × poids × récence`
  (`RECENCY_DECAY`, plancher 0.5), `top_k` 3 → 5. `cosine_search` non modifiée.
- **Étape 5** : `vector.consolidate()` — dedup sémantique par cosinus (≥ 0.98,
  fusion poids max), prune souvenirs faible poids/anciens, O(n²) time-boxé
  (`CONSOLIDATE_MAX_ITER`). Index dérivé uniquement, source jamais touchée.
- **Étape 6** : observabilité (`weight_mean`, `low_weight_ratio`,
  `dedup_estimated`, `last_consolidation`, `consolidation_runs`).

### Audit — correctifs critiques
- **Double-écriture effets de bord** : `services/orchestrator.py` écrivait 2×
  chaque message (copie non déplacée lors du refactor ADR-004). Méthodes
  dupliquées supprimées ; `controllers/routes/jarvis.py` seul point de
  persistance.
- **fastapi non borné** : `pyproject.toml` `fastapi>=0.136` → `>=0.136,<0.137`
  (alignement sur le pin `requirements.txt`), évite le drift de reproductibilité.
- **PII non scrubbée** : `search_documents()` renvoyait le texte indexé en
  clair ; `scrub()` appliqué avant renvoi.
- **Erreurs masquées en 200** : `controllers/routes/jarvis.py` remonte
  désormais un vrai `500` au lieu d'un `200` avec message d'erreur inline.
- **Retry Ollama mort** : boucle de retry inatteignable (`attempt < 0`) rendue
  réellement fonctionnelle (`max_retries=3` configurable).

### Nettoyage
- 12 scripts orphelins, doublons `requirements-reference.txt`/
  `config/requirements.txt`, docs d'audit et plans archivés (`docs/archive/`),
  skills dupliqués consolidés. ~1 Go de cache/artefacts disque supprimés.

### Documentation UX
- Onglet Conversations dédié (existait caché en sidebar, rendu découvrable).
- Blocs d'aide repliables sur les 7 onglets + infobulles sur les boutons.
- Libellés obsolètes corrigés : « LLaVA 8B » → `llama3.2-vision:11b` (frontend
  puis README), « Ollama v0.24.0 » → `v0.30.10`.

### Config modèles
- Toute la config modèle référençait un inventaire fictif (qwen3.6, gemma4,
  deepseek-r1, phi4-mini:3.8b…) → vision 503, embeddings en fallback
  histogramme. Réalignée sur les 6 modèles réellement installés
  (`services/adapters/ollama_adapter.py`, `services/selector.py`,
  `config/*.json`, `scripts/import_gguf.py`).

### Dette technique
- Silent excepts (`controllers/context.py`, `services/diagnostics/checks.py`)
  → loggés en DEBUG au lieu d'être avalés.
- Test mort supprimé (`test_requirements_sources_do_not_diverge`, sources
  supprimées en Phase 2, skip permanent depuis).
- `tests/test_version_consistency.py` : chemin `PROJECT_ROOT` cassé (pointait
  vers un dossier sibling inexistant) → les 2 tests skippaient silencieusement
  depuis leur création. Corrigé, désormais actifs.
- Badge/compteurs de tests README resynchronisés sur l'état réel (573 → 598,
  30 skipped) — étaient retombés obsolètes le jour même de leur premier fix,
  la série mémoire auto-améliorante étant arrivée après.

### Technique
- Suite complète : **598 passed, 30 skipped, 2 xfailed, 0 failed**.
- `ruff check .` : all checks passed.

## [5.0] — 2026-05

### Ajouts
- Python portable Windows embarqué (`portable_python/`)
- Script d'installation Windows (`scripts/install_win.ps1`)
- Routes backend sélectionnable (`POST /api/backend/select`, `GET /api/backend`)
- Skill "trier-et-classer" (PowerShell) enregistré dans le SkillRegistry
- Headers rate-limit standards (`X-RateLimit-Limit`, `X-RateLimit-Remaining`)
- Middleware de sécurité (CSP, X-Frame-Options, X-Content-Type-Options)
- Pagination sur `GET /api/conversations` (`?limit=&offset=`)
- Cache hit rate tracké dans VectorService (`stats().cache_hit_rate`)
- Audit log des requêtes POST (IP + endpoint)
- `CHANGELOG.md` et `.env.example`

### Corrections
- `MODEL_MAP` dans l'adaptateur LLM : noms GGUF alignés sur les fichiers réels
- `WEBUI_SECRET_KEY` : clé en clair → génération aléatoire
- `conversation.py` : écriture atomique (`.tmp` + `os.replace()`)
- `jarvis.py` : `logging.basicConfig` → `LogService`
- `VectorService` : fallback log + déduplication + `is_healthy()` valide + dimension check
- `services/system.py` : `find_python()` OS-aware, `ensure_venv()` gère l'embeddable
- `except Exception: pass` silencieux → `_logger.warning()` dans `vector.py` et `log.py`
- Rate limiter : retourne `(allowed, remaining)` au lieu de `bool`

### Suppressions
- Code mort : classe `Event`, `controllers/routes/__init__.py`
- Librairies GPU : `lib/ollama/cuda_v12/`, `cuda_v13/`, `vulkan/`
- Sections fantômes : `openwebui` dans `adapters.yaml`, `free_llm_enabled` dans `fallback_settings.json`
- Launchers obsolètes : `jarvis.sh` racine, `launchers/launch_jarvis.bat`
- Backend Rust (Shimmy) supprimé : Ollama est désormais le seul backend LLM

### Technique
- 96 tests pytest, 0 erreur
- Score audit : de 77.4% → 87.1%
- ADR-002 : suppression technos inutilisées
- ADR-003 : sandbox Linux CPU-only

## [5.2] — 2026-07-09

### Audit P3.6 — Référencement des ADR
- Index centralisé créé : `docs/adr/README.md` (liste ADR-001 → ADR-005 + principes transverses)
- ADR existants formalisés et cohérents (FastAPI, stockage JSON plat, portabilité mono-utilisateur, pas de Docker, embedding nomic-embed-text-v2-moe)
- Aucun test requis (documentation)

## [5.1] — 2026-07-02

### Audit Qualité Complet (juillet 2026)
- Audit 11 couches, 92 items scorés — **Score global : 78.3%** (72 ✅, 13 ⚠️, 7 ❌, 1 N/A)
- 5 agents : Tech Lead (sect. 2,3,6,8,9), DevOps Local (sect. 4,5,7,10,11), Data/Secu/Docs (doc+sécurité)
- Couche 5 (Configuration) et Couche 7 (Rate Limiting) : **100%** ✅
- Rapport détaillé : `docs/audit-qualite-juillet2026.md`

### Correctifs Prioritaires Appliqués
- **Fix 1** (code mort `LogService.log()`) : remplacé par `_logger.info()` dans `documents.py` et `agents.py`
- **Fix 2** (except silencieux) : `except ValueError: pass` → `_log.warning()` dans `agents.py:117` ; `print()` → `_logger.warning()` dans `pipeline.py:48`
- **Fix 4** (config manquante) : création de `config/.env.example` ; ajout de `.coverage` dans `.gitignore`
- **Fix 9** (endpoints synchrones) : `ingest_documents`, `run_pipeline`, `read_file`, `list_dir`, `find_files` passés en `async def` avec `run_in_executor`
- **Fixes 6-7-8** (PII, réponses JSON, graceful shutdown) : vérifiés OK sans modification
- **24 nouveaux tests** (7 fichiers) pour valider les 9 correctifs — **24/24 ✅**
- **Score audit après correctifs : 86.7%** (+8.4 pts vs 78.3%) — 78 ✅, 12 ⚠️, 0 ❌, 3 N/A
  - 2 ❌ de la v5.0 passés en N/A (PII + commits) : machine cliente hors ligne mono-utilisateur, threat model inexistant
  - Couche Sécurité passée de 75% → **100%**, CI/CD de 57.1% → **83.3%**
