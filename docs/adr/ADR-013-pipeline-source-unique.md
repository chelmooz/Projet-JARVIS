# ADR-013 : Une seule source de vérité pour l'exécution de pipeline

## Statut
Accepté

## Contexte
Deux implémentations coexistaient pour l'exécution d'étapes de pipeline :
- `PipelineService._execute_with_retry` / `_execute_step` dans `services/pipeline.py` (chemin production)
- `execute_pipeline_step` dans `services/pipeline_steps.py` (appelé par `PipelineService` mais aussi testé isolément)

Problèmes identifiés :
1. **Duplication** : ~120 lignes de logique d'étape dupliquée (signature, sélection modèle, forme résultats)
2. **Divergence** : politiques de retry différentes (inconditionnelle vs `on_error=="retry"`), hook habits absent de `pipeline_steps`
3. **Couverture** : `execute_pipeline_step` à 9 % (tests unitaires seulement), `PipelineService` seul chemin production couvert
4. **Agent runner** : `agent_runner` non câblé en production (`controllers/di.py:106`), TODO orphelins dans `pipeline_steps.py:208,210,215`

## Décision
Conserver `PipelineService` (`services/pipeline.py`) comme **unique source de vérité** pour l'exécution de pipeline.
Supprimer `execute_pipeline_step` et les tests qui ne la testaient que (`tests/test_pipeline_steps.py`).

Conserver dans `pipeline_steps.py` uniquement les helpers réutilisés ailleurs :
- `_should_retry`, `_wait_before_retry`, `_runner_supports_model`
- `select_agent`, `select_model`, `retrieve_context`, `query_model`, `save_results`, `format_output`
- `NonCallableRunnerError`

## Conséquences
- `PipelineService` délèguera directement aux helpers de `pipeline_steps.py` (plus d'appel à `execute_pipeline_step`)
- `tests/test_pipeline_steps.py` supprimé (tests de parité migrés vers `tests/test_pipeline_characterization.py`)
- `agent_runner` : paramètre conservé dans `PipelineService.__init__` pour extension future, mais documenté comme non utilisé en production (l'inférence suffit)
- Fichier ADR trace la décision pour éviter réintroduction future

## Validation
Filet de caractérisation `tests/test_pipeline_characterization.py` (10 tests) vert AVANT suppression :
- Contrat d'erreur (state partout, aucune exception frontière)
- Retry conditionnel `on_error=="retry"`
- Hook habits sur succès
- Continuation `on_error=="skip"`
- Runner 3 params reçoit modèle / runner 2 params sans modèle
- Runner non callable → erreur typée
- Max retries respecté

Gates : ruff �� · format �� · mypy �� · pytest --cov �� (52,57 % ≥ 46)