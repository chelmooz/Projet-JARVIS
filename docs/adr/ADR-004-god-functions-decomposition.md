# ADR-004 : God Functions Decomposition

**Statut :** Accepté
**Date :** 2026-06-26
**Décideur :** Tech Lead + équipe JARVIS

## Contexte

OrchestratorService.handle_request() violait le SRP (Single Responsibility Principle)
en mélangeant 3 responsabilités :
1. Exécution métier (routing vision ou AgentGraph)
2. Sauvegarde en conversation (_save_conv)
3. Tracking analytics (_track_query)

De plus, AgentGraph était instancié en dur dans handle_request() au lieu d'être injecté (violation DIP),
et inference.query() retournait `str` alors que chat() retournait `Result` (violation LSP).

## Décision

Trois refactorings sont appliqués :

### 1. SRP — Extraction des effets de bord
- `_save_conv()` et `_track_query()` sont déplacées de OrchestratorService vers le routeur HTTP
- `handle_request()` retourne un résultat pur, sans effets de bord
- La route POST /api/jarvis dans `controllers/routes/jarvis.py` appelle les fonctions de persistance après réception du résultat
- ⚠️ **Correction (audit 2026-07-11)** : initialement il s'agissait d'une *copie* (les deux couches écrivaient → double-écriture en prod). Les méthodes ont été **supprimées** de `services/orchestrator.py` ; le routeur est désormais le **seul** point de persistance (`tests/test_api.py::TestJarvisNoDoubleWrite` verrouille ça : exactement 2 `add_message` par POST réussi).

### 2. DIP — Injection des dépendances
- `AgentGraph` est passé par factory (callable) dans le constructeur d'OrchestratorService
- `select_vision_model` est passé par callable dans le constructeur
- Plus d'instanciation directe dans handle_request()

### 3. LSP — Uniformisation du retour de query()
- `InferencePort.query()` retourne désormais `Result` (comme `chat()`)
- `InferenceService.query()` et tous les adapters concrets sont mis à jour
- Les appelants accèdent au contenu via `result.data.get("response", "")`

## Conséquences

- ✅ Rétrocompatibilité maintenue : les tests existants passent sans modification
- ⚠️ **Mise à jour post-audit** : `tests/test_orchestrator.py` (classes `TestSaveConv`/`TestTrackQuery`, et `test_with_conv_id_saves_messages`) a été adapté car ces méthodes n'existent plus dans l'orchestrateur ; un test d'intégration bout-en-bout (`tests/test_api.py::TestJarvisNoDoubleWrite`) couvre désormais l'écriture unique.
- ✅ Meilleure testabilité : les dépendances sont injectables, les mocks sont plus simples
- ✅ Meilleur respect SOLID : SRP, DIP, LSP
- ⚠️ Les tests qui mockaient `_save_conv` ou `_track_query` directement doivent être mis à jour
- ⚠️ Les tests qui s'attendaient à `query()` retournant `str` doivent être adaptés

## Modules impactés

- `services/orchestrator.py` — handle_request() simplifiée, dépendances injectées
- `controllers/router.py` — reçoit save_conv + track_query dans la route POST /api/jarvis
- `ports/inference.py` — query() retourne Result
- `services/inference.py` — query() retourne Result
- `services/adapters/*.py` — chaque adapter retourne Result
- `controllers/context.py` — passage des dépendances au constructeur
