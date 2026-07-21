"""Recherche par similarité cosinus sur un index vectoriel.

Responsabilité unique (SRP) : calculer le score de similarité entre un
vecteur de requête et les embeddings indexés, puis trier et tronquer aux
top-k résultats les plus proches.
"""
import numpy as np


def cosine_search(query_vector: list[float] | np.ndarray, documents: list[dict], top_k: int = 5) -> list[dict]:
    """Retourne les top_k documents les plus similaires à la requête.

    Calcule un score de similarité par produit scalaire (cosinus sur des
    vecteurs de même dimension), ignore les documents sans embedding ou de
    dimension incompatible, trie par score décroissant et tronque à top_k.
    """
    query_vec = np.array(query_vector, dtype=np.float32)
    query_dim = len(query_vec)
    results = []
    for doc in documents:
        emb = doc.get("embedding")
        if emb is None or len(emb) != query_dim:
            continue
        doc_vec = np.array(emb, dtype=np.float32)
        sim = float(np.dot(query_vec, doc_vec))
        results.append({"text": doc["text"], "metadata": doc.get("metadata", {}), "score": round(sim, 4)})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
