"""WeightConsolidator — pondération, consolidation et ranking des souvenirs.

Responsabilité unique (SRP) : ajuster les poids de feedback, fusionner les
doublons sémantiques (dedup), élaguer les souvenirs anciens/légers (prune), et
pondérer+ranker les résultats de recherche par poids et récence.
"""
import numpy as np

from config.constants import RECENCY_DECAY


class WeightConsolidator:
    """Opère sur la liste ``documents`` de l'index (pondération + consolidation)."""

    def __init__(self, documents: list[dict]):
        self._docs = documents

    def apply_weight(self, conv_id: str, msg_id: str, delta: float,
                    wmin: float, wmax: float) -> int:
        """Applique delta (clampe) au doc matching. Retourne 0/1."""
        for doc in self._docs:
            meta = doc.get("metadata", {})
            if meta.get("conv_id") == conv_id and meta.get("msg_id") == msg_id:
                meta["weight"] = max(wmin, min(wmax, meta.get("weight", 1.0) + delta))
                return 1
        return 0

    def preceding_user_msg_id(self, conversations, conv_id: str, msg_id: str):
        """Retourne l'id du message utilisateur précédent dans la conversation."""
        if conversations is None:
            return None
        conv = conversations.get_conversation(conv_id)
        if not conv:
            return None
        msgs = conv.get("messages", [])
        for i, m in enumerate(msgs):
            if m.get("id") == msg_id and i > 0:
                return msgs[i - 1].get("id")
        return None

    @staticmethod
    def _normalize(emb) -> np.ndarray:
        return np.array(emb, dtype=np.float32) / (np.linalg.norm(emb) or 1.0)

    def dedup(self, sim_threshold: float, max_pairs: int) -> set:
        """Retourne l'ensemble des index à fusionner (doublons sémantiques)."""
        to_remove = set()
        pair_count = 0
        for i in range(len(self._docs)):
            emb_i = self._docs[i].get("embedding")
            if emb_i is None or i in to_remove or pair_count >= max_pairs:
                continue
            norm_i = self._normalize(emb_i)
            for j in range(i + 1, len(self._docs)):
                if pair_count >= max_pairs:
                    break
                emb_j = self._docs[j].get("embedding")
                if emb_j is None or j in to_remove:
                    continue
                pair_count += 1
                if float(np.dot(norm_i, self._normalize(emb_j))) >= sim_threshold:
                    w_i = self._docs[i].get("metadata", {}).get("weight", 1.0)
                    w_j = self._docs[j].get("metadata", {}).get("weight", 1.0)
                    self._docs[i]["metadata"]["weight"] = max(w_i, w_j)
                    to_remove.add(j)
        return to_remove

    def prune(self, prune_weight: float, grace_hours: float, now: float) -> list:
        """Retourne les documents conservés (prune des souvenirs légers/anciens)."""
        kept = []
        for doc in self._docs:
            meta = doc.get("metadata", {})
            weight = meta.get("weight", 1.0)
            created_at = meta.get("created_at", now)
            age_hours = (now - created_at) / 3600.0
            if meta.get("source") == "conversation" and weight <= prune_weight and age_hours > grace_hours:
                continue
            kept.append(doc)
        return kept

    def score_and_rank(self, all_results: list, top_k: int, now: float) -> list:
        """Pondère par poids + récence, trie et tronque aux top_k."""
        scored = []
        for r in all_results:
            meta = r.get("metadata", {})
            weight = float(meta.get("weight", 1.0))
            age_hours = (now - meta.get("created_at", now)) / 3600.0
            recency = max(0.5, 1.0 - RECENCY_DECAY * age_hours)
            scored.append({**r, "score": round(r["score"] * weight * recency, 4)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
