# ADR-003 : Mode sandbox Linux CPU-only

**Statut :** Partiellement obsolète (mis à jour Phase 7)
**Date :** 2026-05-28
**Décideur :** Tech Lead + équipe JARVIS

> ⚠️ **CORRECTIF Phase 7 :** Le serveur Rust dédié (Shimmy) mentionné dans les alternatives
> a été **supprimé** du codebase. L'architecture repose désormais exclusivement sur
> Ollama portable + Python embarqué. Ignorer toute référence à Shimmy.

## Contexte

JARVIS doit fonctionner sur clé USB, branchée sur n'importe quelle machine Linux sans GPU. L'environnement est sandboxé : pas d'accès au réseau après installation, pas de dépendances système.

## Décision

1. **CPU-only prioritaire** : tous les modèles sont quantifiés (Q4_K_M) pour tourner sur CPU
2. **Backend unique : Ollama** (portable, performant sur CPU)
3. **Portable Python** embarqué dans `portable_python/` pour les systèmes sans Python
4. **Tous les chemins relatifs** : la clé USB peut être montée n'importe où

## Conséquences

- ✅ Zéro installation système
- ✅ Fonctionne sur n'importe quel Linux x86_64
- ✅ Les modèles raisonnement (DeepHat V1 7B, Foundation-Sec 8B) sont lents mais fonctionnent
- ❌ Pas de GPU = pas de grands modèles (>13B)
- ❌ Les modèles vision (Llama-3.2-11B-Vision) sont utilisables mais lents

## Alternatives

- Ollama + GPU : nécessite CUDA, pas portable
- Serveur Rust dédié (Shimmy) : **supprimé en Phase 7**, voir correctif ci-dessus
