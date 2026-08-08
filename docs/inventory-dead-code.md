# Inventaire du code mort / non câblé — MT-D2

> But : suite au MT-D1 (suppression de `skill_registry.py` + `models.Skill`),
> ce document dresse l'inventaire du code non référencé détecté par analyse
> statique (`vulture --min-confidence 60`) et le classe en **faux positifs**
> (à conserver) vs **code réellement mort** (supprimé).
>
> Méthode : `vulture` signale les symboles non référencés ; chaque signal a
> été vérifié manuellement (grep des imports/références réelles) car vulture
> ne voit pas certains patterns (décorateurs FastAPI, accès attributs
> dynamiques `paths.X`, stubs d'interface, champs dataclass).

## 1. Code réellement mort → SUPPRIMÉ (MT-D2)

| Élément | Preuve de mortalité | Action |
|---------|---------------------|--------|
| `services/consolidation.py` (`class Consolidator`) | Référencé **uniquement** par `tests/test_consolidation.py`. Aucun import en production (`graph/agent_graph.py` importe `pipeline_steps`, pas `consolidation`) ; `vector.py` possède sa propre méthode `consolidate` (distincte). | Fichier + test supprimés |
| `SelectorService` (`services/selector.py:135-145`) | Façade sans état réel, **jamais instanciée** ni importée ailleurs. `test_selector.py` n'importe pas la classe. Les fonctions pures `select_model`/`select_vision_model` (niveau module) restent et sont bien utilisées. | Classe retirée du module |

> Impact : zéro régression attendue (les symboles supprimés n'avaient aucun
> appelant en production). Vérifié par `ruff` + `pytest` complets.

## 2. Faux positifs vulture → CONSERVÉS (expliqués)

### 2a. Handlers FastAPI (décorateurs non tracés par vulture)
Tous les `controllers/routes/*.py` sont enregistrés dynamiquement dans
`controllers/router.py` via `app.include_router(<module>.router)`. vulture ne
suit pas la référence créée par `@router.get(...)`, d'où les ~40 alerts
`unused function` sur `list_skills`, `toggle_skill`, `get_analytics`,
`create_conversation`, etc. **Ces routes sont bien câblées** — `router.py`
est l'app réelle (il appelle `build_app()` puis `include_router` pour tous
les sous-routeurs). → Conserver.

### 2b. Fonctions middleware imbriquées (`controllers/context.py`)
`_slow_endpoint_profiler`, `_audit_log_middleware`, `_security_headers_middleware`,
`_rate_limit_middleware` sont passées à `app.add_middleware(...)` dans
`_setup_middlewares`. Référencées localement → conserver.

### 2c. Constantes `config/paths.py`
`OLLAMA_HOST`, `MODELS_OLLAMA`, `LOG_FILE`, etc. signalées « unused » mais
**utilisées** : `scripts/import_gguf.py` fait `paths.OLLAMA_HOST` /
`paths.MODELS_OLLAMA`, et `config/logging.yaml` utilise `{{ LOG_FILE }}`
(templating). vulture ne suit pas l'accès attribut `paths.X`. → Conserver.

### 2d. Champs dataclass (`models/__init__.py`)
`system_prompt`, `suggested_skill` sont des champs de `@dataclass` (pas des
variables libres). → Conserver.

### 2e. Stubs d'interface / méthodes de contrat (`ports/*`, `inference.list_backends`, etc.)
Méthodes déclarées par les interfaces (ports) ou non implémentées volontairement
(`incr_errors`, `list_backends`, `register`). Font partie du contrat de conception. → Conserver.

## 3. Symboles testés mais sans appelant en production → CONSERVÉS (API publique)

Ces fonctions/méthodes ne sont référencées qu'en tests (ou dans des routes non
encore branchées), mais constituent l'API publique testée du module. Risque de
suppression élevé pour peu de gain ; à conserver ou à câbler explicitement
ultérieurement :

- `services.selector.recommend_model` (testé, pas encore appelé en prod)
- `services.sanitize.safe_model_name` / `safe_path_segment` / `strip_data_uri` / `safe_json_key`
- `services.file_system.FileSystemService.is_authorized` (testé)
- `services.profiling.reset_profiling` (helper de test)
- `services.analysis.Analyzer.violations` (propriété, non lue)

> Recommandation DevOps : soit câbler ces symboles à un point d'appel réel
> (ex. `recommend_model` exposé via `/api/models/recommend`), soit les
> marquer `@deprecated`/supprimer avec leurs tests si le besoin n'existe pas.

## 4. Conclusion

Le dépôt ne contient plus de module mort de premier plan après MT-D1 + MT-D2.
Les alertes restantes de vulture sont des artefacts de détection (FastAPI, attributs
dynamiques, interfaces) et des API publiques testées — aucune action destructive
supplémentaire justifiée sans câblage explicite.

## 5. MT-D3 — Fichier orphelin détecté (audit externe)

| Élément | Preuve de mortalité | Action |
|---------|---------------------|--------|
| `services/kill_coding.py` (`KillCodingAnalyzer`, `KillCodingReport`) | Shim de réexport créé lors du renommage Kill Coding → Analysis (`services/analysis.py`). Zéro import ailleurs dans le dépôt (`controllers/routes/kill_coding.py` importe directement `Analyzer` depuis `services.analysis`, pas depuis ce shim). Non détecté par vulture (module valide, juste jamais importé — hors du périmètre de détection symbole par symbole). | ✅ **Supprimé (08/08/2026, MT-D4)** — vérification grep exhaustive : aucun `import services.kill_coding` / `KillCodingAnalyzer`/`KillCodingReport` hors du shim. L'absence du module est figée par `tests/test_dead_config_api_removed.py`. |

> Méthode complémentaire à vulture : recherche par module, pour chaque fichier
> source, d'un `import <module>` ou `from <module> import` ailleurs dans le
> dépôt. Un seul fichier n'avait aucune référence externe.

## 6. MT-D4 — API typée `config/__init__.py` supprimée (08/08/2026)

| Élément | Preuve de mortalité | Action |
|---------|---------------------|--------|
| `config/__init__.py` — `ConfigError`, dataclasses (`AgentProfileConfig`, `ModelPreference`, `CyberWorkflow`, `ComponentAsset`, `ComponentsConfig`), getters (`get_agent_profiles`, `get_model_preferences`, `get_cyber_workflows`, `get_components`), `reload`, `_load_json` | API de chargement typée **jamais consommée** : grep exhaustif (production, `controllers/`, `services/`, `scripts/`, `tests/`) → aucun import de ces symboles depuis le package racine `config`. Les sous-modules utilisés sont des fichiers séparés : `config/constants.py`, `config/paths.py`, `config/agent_profiles.py` (le lecteur CORRECT de `agent_profiles.json`, créé en W-DEPLOY-6 — l'ancien getter attendait une liste là où le fichier est un dict, bug latent D6.3). | Le package racine est réduit à un docstring de routage vers les sous-modules ; `test_dead_config_api_removed.py` fige l'absence des symboles. **Fermé : D6.3 du BACKLOG enfin traité.** |

