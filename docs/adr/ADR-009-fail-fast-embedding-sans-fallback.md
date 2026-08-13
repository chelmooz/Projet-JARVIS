# ADR-009 — Fail-Fast sur l'embedding, sans fallback histogramme

- **Statut :** Accepté
- **Date :** 2026-07-24
- **Auteur :** Tech Lead / DevOps (JARVIS)

## Contexte

Le pipeline RAG de JARVIS dépend du backend d'embedding (Ollama + `nomic-embed-text-v2-moe`, 768d) pour la recherche sémantique. Historiquement, un mécanisme de **fallback histogramme** (16 bins) était utilisé lorsque Ollama était indisponible, permettant un fonctionnement dégradé du RAG.

Cependant, ce fallback posait plusieurs problèmes majeurs :

1. **Incompatibilité dimensionnelle** : les vecteurs histogramme (16 dimensions) étaient stockés dans le même index que les embeddings nominaux (768 dimensions), causant :
   - Des crashes lors de la recherche cosinus (dimension mismatch)
   - Une corruption silencieuse de `vector_index.json`
   - Des résultats de recherche aberrants ou vides

2. **Fausse résilience** : le fallback produit des vecteurs de très mauvaise qualité sémantique, donnant l'illusion d'un fonctionnement normal alors que les résultats étaient inutilisables

3. **Complexité inutile** : gestion d'un état mutable (`self.using_fallback`) et d'une logique de basculement complexe

## Décision

**Adopter un principe Fail-Fast** : si le backend d'embedding est indisponible, lever une exception explicite (`RuntimeError`) plutôt que de retourner des données corrompues ou de qualité insuffisante.

### Implémentation

| Composant | Changement | Fichier |
|---|---|---|
| Embedder | Suppression du fallback histogramme, levée explicite de `RuntimeError` | `services/vector_embedder.py` |
| VectorService | Utilisation de l'Embedder refactoré, suppression de `self.using_fallback` | `services/vector.py` |
| Stats | `using_fallback: False` (toujours) dans `stats()` | `services/vector.py:529` |

### Comportement nominal

```python
# Dans services/vector_embedder.py
def embed(self, text: str) -> list[float]:
    try:
        return self._inference.embed(text)
    except RuntimeError as e:
        _logger.critical("ÉCHEC CRITIQUE d'embedding")
        raise RuntimeError(
            "Le moteur de recherche sémantique (RAG) est temporairement indisponible."
        ) from e
```

### Conséquences pour l'utilisateur

- **Si Ollama est indisponible** : la recherche RAG renvoie une erreur explicite plutôt que des résultats erronés
- **Pas de dégradation silencieuse** : l'utilisateur sait immédiatement que la fonctionnalité est indisponible
- **Intégrité des données** : `vector_index.json` reste cohérent (tous les vecteurs sont 768d)

## Conséquences

### Positives

✅ **Intégrité des données** : plus de corruption de l'index vectoriel par des dimensions incompatibles
✅ **Transparence** : l'utilisateur est informé explicitement des échecs
✅ **Simplicité** : suppression de ~50 lignes de code de fallback et de gestion d'état
✅ **Maintenabilité** : code plus simple, plus facile à tester et à auditer
✅ **Alignement SOLID** : Embedder devient stateless, respect du Single Responsibility Principle

### Négatives

❌ **Moins de résilience** : la recherche RAG devient complètement indisponible si Ollama est down
❌ **Expérience utilisateur** : pas de fonctionnement dégradé (mais les résultats dégradés étaient pires que rien)

## Alternatives envisagées

1. **Garder le fallback histogramme** : rejeté car cause des crashes et corruption de données
2. **Fallback vers un autre modèle local** : rejeté car ajoute de la complexité et des dépendances
3. **Fallback vers recherche keyword** : rejeté car change complètement la nature de la recherche (sémantique → lexicale)
4. **Cache agressif des embeddings** : déjà implémenté via `VectorCache`, atténue partiellement le problème

## Voir aussi

- **ADR-005** — Pipeline RAG pour runbooks (référence ce ADR pour le correctif)
- **ADR-006** — Fallback embeddings histogramme (remplacé par ce ADR)
- **VectorService** — `services/vector.py` (implémentation principale)
- **Embedder** — `services/vector_embedder.py` (implémentation Fail-Fast)
