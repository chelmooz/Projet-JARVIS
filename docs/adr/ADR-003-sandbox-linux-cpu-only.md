# ADR-003 : Mode sandbox Linux CPU-only

**Statut :** Partiellement obsolète (mis à jour Phase 7)
**Date :** 2026-05-28
**Décideur :** Tech Lead + équipe JARVIS

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
- ✅ Les modèles lourds (ornith-1.0-9b) sont lents mais fonctionnent
- ❌ Pas de GPU = pas de grands modèles (>13B)
- ❌ Les modèles vision (llama3.2-vision) sont utilisables mais lents

## Alternatives

- Ollama + GPU : nécessite CUDA, pas portable
- Serveur Rust dédié (Shimmy supprimé en phase 7)
