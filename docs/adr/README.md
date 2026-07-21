# Index des ADR — JARVIS Portable

Ce dossier regroupe les **Architectural Decision Records** (ADR) du projet JARVIS.
Format standard : **Statut**, **Contexte**, **Décision**, **Conséquences**.

## Liste des ADR

| ID | Titre | Statut | Fichier |
|----|-------|--------|---------|
| ADR-001 | Architecture MVC + Ports (KISS avec contrats) | Accepté | [ADR-001-architecture-mvc-ports.md](ADR-001-architecture-mvc-ports.md) |
| ADR-002 | Suppression des technos non utilisées | Accepté | [ADR-002-suppression-technos-inutilisees.md](ADR-002-suppression-technos-inutilisees.md) |
| ADR-003 | Mode sandbox Linux CPU-only (portabilité mono-utilisateur, pas de Docker) | Partiellement obsolète | [ADR-003-sandbox-linux-cpu-only.md](ADR-003-sandbox-linux-cpu-only.md) |
| ADR-004 | Décomposition des god-functions | Accepté | [ADR-004-god-functions-decomposition.md](ADR-004-god-functions-decomposition.md) |
| ADR-005 | Runbook du pipeline RAG | Accepté | [ADR-005-runbook-rag-pipeline.md](ADR-005-runbook-rag-pipeline.md) |
| ADR-006 | Fallback embeddings histogramme | Accepté | [ADR-006-fallback-embeddings-histogramme.md](ADR-006-fallback-embeddings-histogramme.md) |
| ADR-007 | Sécurité du mode offline single-backend | Accepté | [ADR-007-securite-offline-single-backend.md](ADR-007-securite-offline-single-backend.md) |

## Décisions transverses du projet

Ces principes, rappelés dans `docs/architecture.md` et le `CHANGELOG.md`, guident les ADR ci-dessus :

- **FastAPI** comme framework web (routeurs `controllers/`, schémas Pydantic).
- **Stockage fichier JSON plat** (conversations, agents) avec écriture atomique (`.tmp` + `os.replace()`).
- **Portabilité mono-utilisateur** : Python embarqué (`portable_python/`), chemins relatifs, clé USB.
- **Pas de Docker** : exécution locale directe, aucune dépendance conteneur.
- **Embedding** : `nomic-embed-text-v2-moe` (768d) via Ollama, fallback histogramme si indisponible.

## Procédure d'ajout

1. Créer `ADR-00N-sujet.md` au format standard.
2. Ajouter une ligne dans le tableau ci-dessus.
3. Référencer l'ADR dans `CHANGELOG.md`.
