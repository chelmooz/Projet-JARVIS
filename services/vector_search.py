"""Recherche vectorielle — Similarité cosinus optimisée (NumPy vectorisé).

Refacto Performance / KISS (15.1) :
- La matrice des embeddings est construite et L2-normalisée une fois
  (``build_normalized_matrix``), puis réutilisée entre requêtes via le cache
  du service (invalidation à chaque mutation de l'index VectorService).
- ``rank_matrix`` calcule le cosinus à partir de la matrice normalisée.
- ``cosine_search`` reste une pure function pour usage direct (tests isolés).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def build_normalized_matrix(
    documents: list[dict[str, Any]], query_dim: int
) -> tuple[list[dict[str, Any]], np.ndarray | None]:
    """Filtre les documents valides et construit la matrice L2-normalisée float32.

    Returns:
        (valid_docs, matrix) où ``matrix`` est ``None`` si aucun embedding valide.
    """
    valid_docs: list[dict[str, Any]] = []
    valid_embeddings: list[list[float]] = []

    for doc in documents:
        emb = doc.get("embedding")
        if emb is not None and len(emb) == query_dim:
            valid_docs.append(doc)
            valid_embeddings.append(emb)

    if not valid_embeddings:
        return valid_docs, None

    matrix = np.array(valid_embeddings, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # évite les NaN sur vecteur nul
    return valid_docs, matrix / norms


def rank_matrix(
    query_vector: list[float] | np.ndarray,
    valid_docs: list[dict[str, Any]],
    matrix: np.ndarray | None,
    top_k: int = 5,
    sim_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Classe les documents par cosinus contre la matrice déjà normalisée.

    Utilise le calcul matriciel vectorisé (C-level BLAS) et ``np.argpartition``
    O(N) pour le Top-K, puis un tri sur le petit sous-ensemble.

    ``sim_threshold`` : les documents dont la similarité est strictement sous
    ce seuil sont exclus avant le classement (anti-hallucination RAG).
    """
    if top_k <= 0 or matrix is None or matrix.shape[0] == 0:
        return []

    query_vec = np.asarray(query_vector, dtype=np.float32)
    if query_vec.size == 0:
        return []

    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []
    similarities = (matrix @ query_vec) / query_norm

    keep = similarities >= sim_threshold
    if not keep.any():
        return []
    filtered_docs = [doc for doc, ok in zip(valid_docs, keep) if ok]
    filtered_sim = similarities[keep]

    k = min(top_k, filtered_sim.size)
    top_indices = np.argpartition(-filtered_sim, k - 1)[:k]
    top_indices = top_indices[np.argsort(-filtered_sim[top_indices])]

    return [
        {
            "text": filtered_docs[i]["text"],
            "metadata": filtered_docs[i].get("metadata", {}),
            "score": float(round(float(filtered_sim[i]), 4)),
        }
        for i in top_indices
    ]


def cosine_search(
    query_vector: list[float] | np.ndarray,
    documents: list[dict[str, Any]],
    top_k: int = 5,
    sim_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Retourne les top_k documents les plus similaires à la requête.

    Construit la matrice normalisée des documents puis la classe (identique
    à la recherche via cache de ``VectorService``, sans le cache).
    """
    if not documents or top_k <= 0:
        return []

    query_vec = np.asarray(query_vector, dtype=np.float32)
    if query_vec.size == 0:
        return []

    valid_docs, matrix = build_normalized_matrix(documents, len(query_vec))
    return rank_matrix(query_vec, valid_docs, matrix, top_k, sim_threshold)


__all__ = ["build_normalized_matrix", "rank_matrix", "cosine_search"]
