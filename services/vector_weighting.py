"""WeightConsolidator — pondération, consolidation et ranking des souvenirs.

Responsabilité unique (SRP) : ajuster les poids de feedback, fusionner les
doublons sémantiques (dedup), élaguer les souvenirs anciens/légers (prune), et
pondérer+ranker les résultats de recherche par poids et récence.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from config.constants import RECENCY_DECAY


class WeightConsolidator:
    """Opère sur la liste ``documents`` de l'index (pondération + consolidation)."""

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._docs = documents

    def apply_weight(self, conv_id: str, msg_id: str, delta: float, wmin: float, wmax: float) -> int:
        """
        Applique delta (clampe) au document correspondant. 
        Retourne 1 si trouvé et modifié, 0 sinon.
        """
        for doc in self._docs:
            meta = doc.get("metadata", {})
            if meta.get("conv_id") == conv_id and meta.get("msg_id") == msg_id:
                current_weight = float(meta.get("weight", 1.0))
                meta["weight"] = max(wmin, min(wmax, current_weight + delta))
                return 1
        return 0

    def preceding_user_msg_id(self, conversations: Any, conv_id: str, msg_id: str) -> str | None:
        """
        Retourne l'ID du message précédent dans la conversation, ou None.
        Note : Délègue la logique de récupération au service de conversation injecté.
        """
        if conversations is None:
            return None
        conv = conversations.get_conversation(conv_id)
        if not conv:
            return None
        msgs = conv.get("messages", [])
        for i, m in enumerate(msgs):
            if m.get("id") == msg_id and i > 0:
                return str(msgs[i - 1].get("id"))
        return None

    @staticmethod
    def _normalize(emb: list[float] | np.ndarray) -> np.ndarray:
        """Normalise un vecteur d'embedding (norme L2). Évite la division par zéro."""
        arr = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(arr)
        return arr / norm if norm > 0 else arr

    def dedup(self, sim_threshold: float, max_pairs: int) -> set[int]:
        """
        Retourne l'ensemble des index à fusionner (doublons sémantiques).
        Limite le nombre de comparaisons à `max_pairs` pour éviter une complexité O(N²) infinie.
        Modifie inplace le poids du document conservé (max des deux poids).
        """
        to_remove: set[int] = set()
        pair_count = 0
        n_docs = len(self._docs)

        for i in range(n_docs):
            emb_i = self._docs[i].get("embedding")
            if emb_i is None or i in to_remove or pair_count >= max_pairs:
                continue

            norm_i = self._normalize(emb_i)

            for j in range(i + 1, n_docs):
                if pair_count >= max_pairs:
                    break

                emb_j = self._docs[j].get("embedding")
                if emb_j is None or j in to_remove:
                    continue

                pair_count += 1
                similarity = float(np.dot(norm_i, self._normalize(emb_j)))

                if similarity >= sim_threshold:
                    meta_i = self._docs[i].get("metadata", {})
                    meta_j = self._docs[j].get("metadata", {})
                    w_i = float(meta_i.get("weight", 1.0))
                    w_j = float(meta_j.get("weight", 1.0))
                    meta_i["weight"] = max(w_i, w_j)
                    to_remove.add(j)

        return to_remove

    def prune(self, prune_weight: float, grace_hours: float, now: float) -> list[dict[str, Any]]:
        """
        Retourne les documents conservés (élagage des souvenirs de conversation légers et anciens).
        """
        kept: list[dict[str, Any]] = []
        for doc in self._docs:
            meta = doc.get("metadata", {})
            weight = float(meta.get("weight", 1.0))
            created_at = float(meta.get("created_at", now))
            age_hours = (now - created_at) / 3600.0

            is_conv = meta.get("source") == "conversation"
            is_old_and_light = weight <= prune_weight and age_hours > grace_hours

            if is_conv and is_old_and_light:
                continue

            kept.append(doc)
        return kept

    def score_and_rank(self, all_results: list[dict[str, Any]], top_k: int, now: float) -> list[dict[str, Any]]:
        """
        Pondère par poids et récence, trie par score décroissant et tronque aux top_k.
        """
        scored: list[dict[str, Any]] = []
        for r in all_results:
            meta = r.get("metadata", {})
            weight = float(meta.get("weight", 1.0))
            created_at = float(meta.get("created_at", now))
            age_hours = (now - created_at) / 3600.0
            recency = max(0.5, 1.0 - RECENCY_DECAY * age_hours)

            base_score = float(r.get("score", 0.0))
            new_score = round(base_score * weight * recency, 4)

            scored.append({**r, "score": new_score})

        scored.sort(key=lambda x: float(x["score"]), reverse=True)
        return scored[:top_k]


__all__ = ["WeightConsolidator"]
