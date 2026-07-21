# ADR-006 : Fallback embeddings histogramme

**Statut :** Accepté
**Date :** 2026-07-20
**Décideur :** Data/Sécu/Docs + équipe JARVIS

## Contexte

Le embeddings vectoriel repose sur `nomic-embed-text-v2-moe` (768d) servi par Ollama
(`services/vector_embedder.py`). Si Ollama ou le modèle d'embedding est injoignable
(clef hors ligne sans modèle tiré, crash du serveur), la recherche sémantique (RAG)
tombe en panne et casse l'expérience utilisateur.

## Décision

`VectorEmbedder` implémente un **fallback déterministe** basé sur un histogramme de
tokens (hashing tf) quand l'embedding Ollama échoue. Le fallback :
- est calculé localement, sans réseau ;
- produit un vecteur de dimension fixe ;
- est signalé via `using_fallback` (exposé par `VectorService._using_fallback`) pour
  que l'UI/les logs indiquent une qualité de similarité dégradée mais fonctionnelle.

L'embedding Ollama reste la source de vérité dès qu'il redevient disponible (aucune
action utilisateur requise, le prochain `index`/`search` réessaie Ollama).

## Conséquences

- ✅ RAG jamais totalement hors service : au pire, similarité approximative.
- ✅ Comportement offline-first respecté (aucune dépendance réseau en fallback).
- ⚠️ La qualité de recherche en mode fallback est inférieure (pas de sémantique
  réelle) — documenté comme limitation connue, pas un bug.
- ✅ Aucun nouveau paramètre exposé à l'utilisateur.

## Modules impactés

- `services/vector_embedder.py` — `_fallback_embed` + bascule automatique.
- `services/vector.py` — `VectorService._using_fallback` délègue vers l'embedder.
