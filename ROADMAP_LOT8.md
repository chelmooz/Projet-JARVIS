# ROADMAP_LOT8 — Plan d'exécution pour opencode

Dépôt cible : `chelmooz/Projet-JARVIS` (Python 3.12, FastAPI, MVC + Ports ; front vanilla JS dans `static/`).
Rôle attendu de l'agent : codeur KISS en TDD strict, une micro-tâche = un commit.

## 0. Règles permanentes (à relire avant chaque tâche)

1. Cycle obligatoire : **RED** (test écrit et vu échouer) → **GREEN** (code minimal) → **REFACTOR** (sans toucher aux assertions).
2. Gates avant chaque commit, dans cet ordre :
   `ruff check .` · `ruff format --check .` · `mypy` · `pytest --cov`
3. Un commit conventionnel par micro-tâche, un seul sujet. Diff ≤ 200 lignes. Stop et rapport si > 60 min.
4. Aucune assertion existante modifiée ; seuls les chemins d'`import` et de `patch()` peuvent suivre un déplacement de module.
5. Aucun test qui touche le réseau, Ollama ou le disque hors `tmp_path`.
6. KISS : aucune abstraction sans un deuxième appelant réel. Aucune couche « au cas où ».
7. Quand deux implémentations de la même règle coexistent, l'une disparaît dans la même micro-tâche. Jamais de branche de compatibilité.
8. Objectif de lisibilité, pas de compteur : viser des fonctions courtes à responsabilité unique ; redécouper seulement si la lisibilité y gagne.
9. Ne jamais recréer de code « à l'identique supposé ». Si un fichier manque, en retrouver la source ou déduire le contrat des usages, et le verrouiller par un test de contrat.
10. Après chaque lot : mettre à jour `ROADMAP.md` + `BACKLOG.md` avec le hash de commit et les chiffres réellement mesurés.

## 1. État vérifié du dépôt (baseline, ne pas refaire l'analyse)

- 248 fichiers, dont 153 Python (~18,7 k lignes) et 24 modules JS applicatifs (~2,9 k lignes).
- `ruff check .` passe. `ruff format --check .` échoue sur `tests/test_pipeline_steps.py`.
- `pytest` **ne collecte pas** : `ImportError: cannot import name 'Result' from 'models'`.
- Cause racine : `.gitignore` ligne 2 contient `models/`. Le package Python `models/` est ignoré en bloc ; seul `models/schemas.py` est tracké. `models/__init__.py` et les DTO `Result`, `Task`, `Pipeline`, `PipeStep` n'ont jamais été committés alors que 9 fichiers les importent (`ports/__init__.py:17`, `ports/pipeline.py:16`, `services/inference.py:8`, `services/pipeline.py:16`, `services/router.py:17`, `services/adapters/ollama_adapter.py:18`, `services/adapters/protocols.py:10`, `tests/conftest.py:16`, `tests/test_router.py:1`).
- `mypy` échoue aussi : `Source file found twice under different module names: "schemas" / "models.schemas"`.
- Couverture Python : **non mesurable** tant que la collecte échoue. `coverage-badge.json` affiche 50,3 %, valeur héritée.
- Front : vitest configuré, 5 fichiers de test pour 16 modules ; `.github/workflows/ci.yml` ne contient aucun job front.
- Duplication métier : `services/pipeline_steps.py:150 execute_pipeline_step` (122 l., 17 branches) n'est appelé que par `tests/test_pipeline_steps.py` ; la logique de production vit dans `services/pipeline.py:271-330` (`_execute_with_retry` / `_execute_step`). Les deux ne sont pas équivalentes (signature, sélection de modèle, forme des résultats).
- Fonctions à découper : `controllers/router.py:141 create_app` (103 l.) · `controllers/middlewares.py:75 setup_middlewares` (91 l.) · `controllers/warmup.py:69 lifespan` (88 l., 13 br.) · `controllers/routes/jarvis.py:116 handle_request` (77 l.) · `services/adapters/http.py:171 _call_with_retry` (63 l., 13 br.) · `services/log.py:77 _load_logs` (47 l., 14 br.) · `services/vector.py:456 search` (64 l.) · `services/system.py:138 ensure_venv` (74 l.).
- Sans tests dédiés : `services/orchestrator.py`, `services/conversation.py`, `services/toolbox.py`, `services/log.py`, `services/adapters/http.py`, `controllers/warmup.py`.
- Notes obsolètes à corriger : `ROADMAP.md` dit `services/ollama_download.py` « non committé » — le fichier est présent au HEAD.
- Dette ouverte : `agents/supervisor.py:55,150` (conventions dupliquées), `controllers/di.py:106` (`agent_runner=None` non tranché), ticket mypy `scripts/schedule_backup.py`.

## 2. Lot A — Débloquer le dépôt (prérequis absolu)

| # | Étape | Livrable / critère |
|---|---|---|
| A1 | RED | `tests/test_import_contract.py` importe `models`, `ports`, `services.pipeline`, `services.router`, `controllers.router`. Échoue avec l'`ImportError` actuel. |
| A2 | GREEN | `.gitignore` : remplacer `models/` par le chemin réel des poids (`models_weights/` ou `/models/*.gguf`, `/models/*.onnx`). Le package Python ne doit plus être ignoré. |
| A3 | GREEN | Committer `models/__init__.py` + les DTO existants **copiés depuis la machine de dev**. S'ils sont perdus, déduire le contrat des usages (`Result.ok`, champs lus dans `inference.py`, `ollama_adapter.py`, `pipeline.py`, `router.py`) et le figer par des tests de contrat. Ne pas dupliquer les DTO Pydantic de `schemas.py`. |
| A4 | GREEN | `git check-ignore -v` sur chaque dossier de code + diff clone frais / arbre local : vérifier qu'aucun autre source n'est masqué. |
| A5 | GREEN | Corriger le double nom de module `schemas` / `models.schemas` par le package explicite, sans `exclude` mypy. `ruff format` sur `tests/test_pipeline_steps.py`. |
| A6 | GREEN | Les 4 gates au vert. Mesurer la couverture réelle et remplacer toute mention de « 49 % » par la valeur mesurée. Régénérer `coverage-badge.json`. |
| A7 | GREEN | Étape CI dans le job `quality` qui échoue si le test de contrat d'import échoue. |

## 3. Lot B — Remettre la documentation en phase avec git

| # | Étape | Livrable / critère |
|---|---|---|
| B1 | — | `git log -- services/ollama_download.py` : corriger `ROADMAP.md` (note « non committé » fausse), cocher 4.4. |
| B2 | GREEN | Re-trier les imports de `tests/test_ollama_installer_security.py` si ruff le signale. Assertions intactes. |
| B3 | — | Cartographie d'usage : graphe d'imports, cycles, modules les plus appelés, hotspots git (`git log --format= --name-only | sort | uniq -c | sort -rn | head -30`). 15 lignes dans `BACKLOG.md`. **Autorisation explicite de réordonner les lots D→F** selon cette carte. |

## 4. Lot C — Une seule source de vérité pour le pipeline

Décision cadrée d'avance : `PipelineService` (`pipeline.py`) est conservé car c'est le seul chemin appelé en production et le seul couvert. `execute_pipeline_step` part.

| # | Étape | Livrable / critère |
|---|---|---|
| C1 | RED | Caractériser le chemin de production : succès d'une étape, propagation du contexte, échec avec `on_error="skip"`, épuisement des retries, ni runner ni inférence configurés. |
| C2 | RED | Tests de parité : chaque comportement métier utile de `execute_pipeline_step` reproduit sur `PipelineService`. **Interdiction de supprimer avant que ce filet soit vert.** |
| C3 | — | `docs/adr/ADR-013-pipeline-source-unique.md`, 15 lignes : décision + motif. |
| C4 | GREEN | Supprimer `execute_pipeline_step` et les tests qui ne testaient que cette fonction morte. Conserver les helpers de `pipeline_steps.py` réellement importés ailleurs. |
| C5 | REFACTOR | Extraire, chacun avec un appelant réel : construction du prompt, appel runner/inférence, extraction de réponse, politique de retry, enregistrement du résultat. |
| C6 | RED/GREEN | Trancher `agent_runner` (`controllers/di.py:106`) : câblé avec un test, ou paramètre et branches mortes retirés. |

## 5. Lot D — Cœur métier avant plomberie

| # | Étape | Livrable / critère |
|---|---|---|
| D1 | ✅ | `services/orchestrator.py` : 16 tests (routage nominal, fallback, vision, métriques, analytics, habitudes, injection DIP) — vue sur remote, CI déclenchée |
| D2 | ✅ | `explicit_package_bases = true` dans `[tool.mypy]` · mypy vert sur 124 sources · `services/pipeline.py:232` corrigé |
| D3 | ✅ | `tests/test_toolbox.py` : 15 tests API publique : `is_enabled`, `describe_tools`, `auto_execute` (triggers fichier/diagnostic), `_extract_target` et `_fold_accents` en fonctions pures — tous verts |
| D4 | ✅ | `tests/test_vector_search.py` : 9 tests via FakeVector/FakeEmbedding : requête vide → [], corpus vide → [], hit de cache, top_k respecté, paliers 1-2, fallback non borné + warning |
| D5 | ✅ | `services/vector.py` : extraction `_run_bounded_search` de la méthode `search` (SRP) — assertions intactes, comportement externe inchangé |

## 6. Lot E — God functions des contrôleurs

| # | Étape | Livrable / critère |
|---|---|---|
| E1 | ✅ | `tests/test_router_e1.py` : 10 tests couvrant `create_app()` — routes (/, /api/status, /api/models, /api/backend, /api/metrics), middlewares (context injection, status_cache, status_lock), contenu |
| E2 | 🟡 | `create_app` → `_register_routes`, `_register_middlewares`, init d'état — en cours (refactoring effectué, tests verts) |
| E3 | 🔴 | `lifespan` : à faire — démarrage dégradé sans Ollama, fermeture propre, échec journalisé sans lever |
| E4 | 🔴 | `lifespan` en étapes nommées testables séparément |
| E5 | 🔴 | `routes/jarvis.py:handle_request` : streaming, non-streaming, erreur agent, payload rejeté |
| E6 | 🔴 | Isoler parsing / appel orchestrateur / construction de réponse. Codes 4xx-5xx et format JSON préservés. |

## 7. Lot F — HTTP et logs

| # | Étape | Livrable / critère |
|---|---|---|
| F1 | RED | `services/adapters/http.py:_call_with_retry` avec transport httpx factice : succès immédiat, retry puis succès, timeout, exception réseau, code non retryable, backoff borné. |
| F2 | REFACTOR | Fonction pure `is_retryable(...)` extraite, politique inchangée. |
| F3 | RED | `services/log.py:_load_logs` : fichier absent, JSON invalide, rotation, filtre de niveau, entrée partiellement malformée. |
| F4 | REFACTOR | Parseur de ligne pur extrait ; lecture / rotation / filtrage séparés. |

## 8. Lot G — Verrou CI front (une tâche = un module)

| # | Étape | Livrable / critère |
|---|---|---|
| G1 | GREEN | Job `frontend` dans `ci.yml` : version Node explicite, `npm ci` puis `npm test` dans `static/`. Vérifié en cassant volontairement un test une fois, puis restauré. |
| G2 | RED/GREEN | Tests `static/assets/js/modules/state.js`. |
| G3 | RED/GREEN | `utils.js`. |
| G4 | RED/GREEN | `status.js`. |
| G5 | RED/GREEN | `files.js`. |
| G6 | RED/GREEN | `settings.js`. |

Priorité aux fonctions pures, aux événements et aux contrats réseau simulés. Pas de tests DOM fragiles.

## 9. Lot H — Nettoyage et cliquet de couverture

| # | Étape | Livrable / critère |
|---|---|---|
| H1 | RED/REFACTOR | `agents/supervisor.py:55,150` : caractériser puis factoriser les conventions dupliquées, retirer les renvois BACKLOG. |
| H2 | GREEN | Ticket mypy `scripts/schedule_backup.py` : une seule stratégie documentée, après vérification des imports. Pas de `scripts/__init__.py` ajouté mécaniquement. |
| H3 | GREEN | `fail_under` en cliquet **montant** : baseline de A6, relevé après chaque lot vert, cible `fail_under = 60` en fin de plan. Badge régénéré depuis la CI. |
| H4 | — | Purger `ROADMAP.md` et `BACKLOG.md` des affirmations obsolètes ; chaque ligne pointe un commit ou une mesure. |

## 10. Ordre d'exécution

```text
A (dépôt cassé)  →  B (docs + cartographie)  →  C (duplication pipeline)
  →  D (cœur métier)  →  E (contrôleurs)  →  F (http/log)  →  G (CI front)  →  H (nettoyage)
```

`A` est bloquant : aucune autre tâche n'est exécutable avant que `pytest` collecte. `B3` peut réordonner `D`, `E`, `F` selon les hotspots.

## 11. Definition of done par micro-tâche

1. Test rouge écrit et vu échouer.
2. Code minimal pour le vert.
3. Refactor sans changer les tests.
4. Les 4 gates vertes.
5. Un commit conventionnel, un seul sujet.
6. Ligne de bilan dans `BACKLOG.md` avec hash et chiffres mesurés.

## Note de contexte

Ce document est destiné au dépôt Python `Projet-JARVIS`, à déposer en `ROADMAP_LOT8.md`. Dites-moi si je le génère comme fichier téléchargeable prêt à copier dans le dépôt.