# ADR-002 : Suppression des technos non utilisées

**Statut :** Accepté
**Date :** 2026-05-28
**Décideur :** Tech Lead + équipe JARVIS

## Contexte

L'audit d'architecture a révélé que 4 technologies étaient référencées dans la doc ou la config mais jamais utilisées dans le code.

## Décision

Supprimer toute référence à ces technologies :

| Technologie | Raison |
|-------------|--------|
| **Grok** | Option UI uniquement, aucun adaptateur backend |
| **FreeLLMAPI** | Dépendance cloud, incompatible offline |
| **LangGraph** | `AgentGraph` est un pipeline séquentiel, pas un StateGraph |
| **Turbovec** | Le vector store utilise Ollama embeddings (nomic-embed-text) + fallback histogramme |

## Conséquences

- ✅ Moins de confusion pour les nouveaux contributeurs
- ✅ Frontend plus clair (2 options de backend au lieu de 4)
- ✅ Économie de maintenance
- ❌ Si un jour on veut ces technos, il faudra les réimplémenter

## Alternatives envisagées

- Les garder en mode "documenté mais pas implémenté" → source de confusion
