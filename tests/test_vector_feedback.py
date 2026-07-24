"""Tests MT 7.4 — Rétropropagation de score sur les chunks.

Vérifie que le feedback modifie les métadonnées des chunks et que 
la consolidation élimine les chunks toxiques.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from services.vector import VectorService


@pytest.fixture
def vector_service():
    """VectorService avec un mock d'inférence pour éviter les vrais appels LLM."""
    mock_inference = MagicMock()
    mock_inference.query.return_value = {"data": {"embedding": [0.1] * 768}}
    
    service = VectorService(inference_service=mock_inference)
    service._data = {"documents": [], "embedding_dim": 768}
    service._message_index = {}
    return service


def test_vector_update_score_modifies_chunk_metadata(vector_service):
    """GREEN : update_score doit modifier le score et bad_count d'un chunk."""
    chunk_id = "test_chunk_1"
    vector_service._data["documents"].append({
        "text": "Contenu du chunk",
        "metadata": {
            "chunk_id": chunk_id,
            "score": 0.0,
            "bad_count": 0,
            "weight": 1.0,
            "created_at": time.time()
        },
        "embedding": [0.1] * 768
    })
    
    vector_service.update_score(chunk_id, -1.0)
    vector_service.update_score(chunk_id, -1.0)
    
    doc = vector_service._data["documents"][0]
    assert doc["metadata"]["score"] == -2.0
    assert doc["metadata"]["bad_count"] == 2


def test_vector_update_score_returns_count(vector_service):
    """GREEN : update_score retourne le nombre de chunks mis à jour (0 ou 1)."""
    count = vector_service.update_score("inexistent_chunk", 1.0)
    assert count == 0
    
    vector_service._data["documents"].append({
        "text": "Contenu",
        "metadata": {
            "chunk_id": "exists", "score": 0.0, "bad_count": 0, 
            "weight": 1.0, "created_at": time.time()
        },
        "embedding": [0.1] * 768
    })
    count = vector_service.update_score("exists", 1.0)
    assert count == 1


def test_vector_consolidate_prunes_toxic_chunks(vector_service):
    """GREEN : consolidate doit supprimer les chunks avec bad_count > 3 ou score < -2.0."""
    now = time.time()
    docs = [
        {
            "text": "Chunk sain",
            "metadata": {
                "chunk_id": "good_1", "score": 1.0, "bad_count": 0, "weight": 1.0,
                "created_at": now, "source": "conversation", "conv_id": "c1", "msg_id": "m1"
            },
            "embedding": [0.1] * 768
        },
        {
            "text": "Chunk toxique score",
            "metadata": {
                "chunk_id": "bad_score", "score": -3.0, "bad_count": 1, "weight": 1.0,
                "created_at": now, "source": "conversation", "conv_id": "c1", "msg_id": "m2"
            },
            "embedding": [0.1] * 768
        },
        {
            "text": "Chunk toxique bad_count",
            "metadata": {
                "chunk_id": "bad_count", "score": -1.0, "bad_count": 4, "weight": 1.0,
                "created_at": now, "source": "conversation", "conv_id": "c1", "msg_id": "m3"
            },
            "embedding": [0.1] * 768
        },
        {
            "text": "Chunk ancien sans score (backward compat)",
            "metadata": {
                "chunk_id": "old_chunk", "weight": 1.0, "created_at": now,
                "source": "conversation", "conv_id": "c1", "msg_id": "m4"
            },
            "embedding": [0.1] * 768
        }
    ]
    vector_service._data["documents"] = docs
    
    # On mock WeightConsolidator pour isoler la logique de toxicité
    with patch("services.vector.WeightConsolidator") as MockWC:
        mock_wc = MagicMock()
        MockWC.return_value = mock_wc
        
        # dedup ne supprime rien
        mock_wc.dedup.return_value = set()
        # prune garde TOUS les documents (on teste uniquement la logique toxique)
        mock_wc.prune.return_value = docs.copy()
        
        vector_service.consolidate()
    
    remaining_ids = [d["metadata"].get("chunk_id") for d in vector_service._data["documents"]]
    
    assert "good_1" in remaining_ids
    assert "old_chunk" in remaining_ids  # Backward compat : pas élagué
    
    assert "bad_score" not in remaining_ids
    assert "bad_count" not in remaining_ids
    
    assert len(vector_service._data["documents"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])