"""Filet de caractérisation — services/vector.py (Lot 3).

VectorService orchestre des collaborateurs déjà testés isolément
(VectorIndex, VectorCache/MatrixCache, DimensionManager, WeightConsolidator,
build_normalized_matrix/rank_matrix, vector_stats). Ce filet ne les refake
pas : ils sont utilisés réels. Seule la frontière externe (inference_service,
ChatPort/EmbeddingPort côté embeddings) est fakée. `VECTOR_PATH` est
monkeypatché vers `tmp_path` sur chaque test (règle #5 : aucun test qui
touche le disque hors tmp_path).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import pytest

import services.vector as vector_module
from config.constants import (
    BAD_COUNT_PRUNING_THRESHOLD,
    CONSOLIDATE_GRACE_HOURS,
    CONSOLIDATE_PRUNE_WEIGHT,
    MAX_VECTOR_DOCS,
    SCORE_PRUNING_THRESHOLD,
    WEIGHT_MAX,
    WEIGHT_MIN,
)
from services.vector import VectorService

# ---------------------------------------------------------------------------
# Double de la frontière externe : le service d'inférence (embeddings).
# ---------------------------------------------------------------------------


class FakeInferenceService:
    """Double du service d'inférence : embeddings contrôlés par texte."""

    def __init__(self, embeddings: dict[str, list[float]] | None = None, default_dim: int = 4) -> None:
        self.embeddings = embeddings or {}
        self.default_dim = default_dim
        self.embed_calls: list[str] = []
        self.batch_calls: list[list[str]] = []
        self.fail_embed_on: set[str] = set()
        self.fail_batch = False

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        if text in self.fail_embed_on:
            raise RuntimeError("backend d'embedding indisponible")
        return list(self.embeddings.get(text, [0.1] * self.default_dim))

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls.append(list(texts))
        if self.fail_batch:
            raise RuntimeError("backend batch indisponible")
        return [list(self.embeddings.get(t, [0.1] * self.default_dim)) for t in texts]


def _make_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inference: Any | None = None,
    prewrite_bytes: bytes | None = None,
) -> VectorService:
    """Construit un VectorService isolé sur tmp_path (VECTOR_PATH monkeypatché)."""
    vpath = tmp_path / "vector_index.json"
    monkeypatch.setattr(vector_module, "VECTOR_PATH", str(vpath))
    if prewrite_bytes is not None:
        vpath.write_bytes(prewrite_bytes)
    return VectorService(inference if inference is not None else FakeInferenceService())


def _vpath(monkeypatch_target: VectorService) -> str:
    return vector_module.VECTOR_PATH


# ---------------------------------------------------------------------------
# _archive_corrupted_file (fonction module, exercée aussi via _load_secure)
# ---------------------------------------------------------------------------


def test_archive_corrupted_file_renames_and_returns_new_path(tmp_path: Path) -> None:
    target = tmp_path / "vector_index.json"
    target.write_bytes(b"not json at all")
    archived = vector_module._archive_corrupted_file(str(target))
    assert archived
    assert not target.exists()
    assert Path(archived).exists()


def test_archive_corrupted_file_missing_path_returns_empty_string(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    assert vector_module._archive_corrupted_file(str(missing)) == ""


def test_archive_corrupted_file_rename_oserror_returns_empty_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "vector_index.json"
    target.write_bytes(b"garbage")

    def _raise_rename(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("rename refusé")

    monkeypatch.setattr(os, "rename", _raise_rename)
    assert vector_module._archive_corrupted_file(str(target)) == ""


# ---------------------------------------------------------------------------
# __init__ / _load_secure / _build_message_index
# ---------------------------------------------------------------------------


def test_init_without_existing_file_starts_with_empty_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    assert svc.stats()["total"] == 0
    assert svc.last_migration == vector_module.MIGRATION_OK


def test_init_loads_valid_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = orjson.dumps(
        {
            "documents": [{"text": "bonjour", "metadata": {}, "embedding": None}],
            "embedding_dim": vector_module.EXPECTED_DIM,
            "embedding_model": vector_module.EXPECTED_MODEL,
        }
    )
    svc = _make_service(monkeypatch, tmp_path, prewrite_bytes=payload)
    assert svc.stats()["total"] == 1
    assert svc.last_migration == vector_module.MIGRATION_OK


def test_init_with_non_dict_json_archives_and_starts_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path, prewrite_bytes=orjson.dumps([1, 2, 3]))
    assert svc.stats()["total"] == 0
    archived = [p for p in tmp_path.iterdir() if ".corrupted." in p.name]
    assert archived


def test_init_with_dict_missing_documents_key_archives_and_starts_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path, prewrite_bytes=orjson.dumps({"foo": "bar"}))
    assert svc.stats()["total"] == 0


def test_init_with_corrupted_json_bytes_archives_and_starts_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path, prewrite_bytes=b'{"documents": [')
    assert svc.stats()["total"] == 0
    archived = [p for p in tmp_path.iterdir() if ".corrupted." in p.name]
    assert archived


def test_init_second_call_on_corrupted_file_does_not_reloop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Caractérise le filet historique (test_vector_corrupted.py) en version isolée tmp_path."""
    vpath = tmp_path / "vector_index.json"
    monkeypatch.setattr(vector_module, "VECTOR_PATH", str(vpath))
    vpath.write_bytes(b'{"documents"')

    VectorService(FakeInferenceService())
    # Le fichier a été archivé (renommé) par le premier appel : le second ne
    # doit pas retrouver de fichier corrompu au même chemin.
    assert not vpath.exists()
    VectorService(FakeInferenceService())
    archived = [p for p in tmp_path.iterdir() if ".corrupted." in p.name]
    assert len(archived) == 1  # un seul archivage, pas une boucle


def test_build_message_index_populates_from_conversation_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = orjson.dumps(
        {
            "documents": [
                {
                    "text": "salut",
                    "metadata": {"source": "conversation", "conv_id": "c1", "msg_id": "m1"},
                    "embedding": None,
                },
                {"text": "note libre", "metadata": {"source": "note"}, "embedding": None},
            ],
            "embedding_dim": None,
        }
    )
    svc = _make_service(monkeypatch, tmp_path, prewrite_bytes=payload)
    # Le message déjà indexé (c1, m1) doit être dédupliqué en O(1).
    svc.index_message("c1", "m1", "user", "salut", ts=1.0)
    assert svc.stats()["total"] == 2  # inchangé : pas de doublon ajouté


# ---------------------------------------------------------------------------
# _save_secure (succès implicite via index(), échecs explicites)
# ---------------------------------------------------------------------------


def test_save_secure_failure_cleans_up_temp_file_and_reraises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    temp_path = vector_module.VECTOR_PATH + ".tmp"

    def _raise_replace(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disque plein")

    monkeypatch.setattr(os, "replace", _raise_replace)
    with pytest.raises(OSError, match="disque plein"):
        svc.index("un document", metadata={})
    assert not os.path.exists(temp_path)


def test_save_secure_failure_cleanup_error_is_swallowed_original_reraised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path)

    def _raise_replace(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("erreur originale")

    def _raise_remove(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("erreur de nettoyage")

    monkeypatch.setattr(os, "replace", _raise_replace)
    monkeypatch.setattr(os, "remove", _raise_remove)
    with pytest.raises(OSError, match="erreur originale"):
        svc.index("un document", metadata={})


# ---------------------------------------------------------------------------
# flush()
# ---------------------------------------------------------------------------


def test_flush_is_noop_when_not_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(svc, "_save_secure", lambda: calls.append(1))
    svc.flush()
    assert calls == []


def test_flush_saves_and_resets_dirty_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(default_dim=4)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("texte à vectoriser")
    svc.vectorize_pending()  # positionne dirty=True puis flush() en interne déjà
    assert svc._dirty is False  # déjà flushé par vectorize_pending

    svc._dirty = True
    calls = []
    original = svc._save_secure

    def _spy() -> None:
        calls.append(1)
        original()

    monkeypatch.setattr(svc, "_save_secure", _spy)
    svc.flush()
    assert calls == [1]
    assert svc._dirty is False


# ---------------------------------------------------------------------------
# preload() / _embed()
# ---------------------------------------------------------------------------


def test_preload_success_does_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService()
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.preload()
    assert "warmup" in inference.embed_calls


def test_preload_failure_is_swallowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService()
    inference.fail_embed_on.add("warmup")
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.preload()  # ne doit pas lever


# ---------------------------------------------------------------------------
# index() / index_batch()
# ---------------------------------------------------------------------------


def test_index_adds_new_document_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("premier document", metadata={"source": "note"})
    assert svc.stats()["total"] == 1
    assert os.path.exists(vector_module.VECTOR_PATH)


def test_index_duplicate_text_is_not_persisted_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("même texte")
    calls = []
    monkeypatch.setattr(svc, "_save_secure", lambda: calls.append(1))
    svc.index("même texte")
    assert svc.stats()["total"] == 1
    assert calls == []  # add_document a retourné False : pas de sauvegarde


def test_index_batch_adds_only_unique_documents_with_single_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    calls = []
    original = svc._save_secure
    monkeypatch.setattr(svc, "_save_secure", lambda: (calls.append(1), original())[-1])
    svc.index_batch([("doc a", None), ("doc b", None), ("doc a", None)])
    assert svc.stats()["total"] == 2
    assert calls == [1]  # un seul appel groupé, pas un par document


def test_index_batch_all_duplicates_skips_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("déjà là")
    calls = []
    monkeypatch.setattr(svc, "_save_secure", lambda: calls.append(1))
    svc.index_batch([("déjà là", None)])
    assert calls == []


# ---------------------------------------------------------------------------
# _embed_pending() / vectorize_pending() / _normalize_embedding()
# ---------------------------------------------------------------------------


def test_normalize_embedding_scales_to_unit_norm() -> None:
    result = VectorService._normalize_embedding([3.0, 4.0])
    assert result == pytest.approx([0.6, 0.8])


def test_normalize_embedding_zero_vector_returned_unchanged() -> None:
    result = VectorService._normalize_embedding([0.0, 0.0, 0.0])
    assert result == [0.0, 0.0, 0.0]


def test_vectorize_pending_embeds_all_pending_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0], "b": [0.0, 1.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.index("b")
    count = svc.vectorize_pending()
    assert count == 2
    assert svc.stats()["embedded"] == 2
    assert inference.batch_calls == [["a", "b"]]


def test_vectorize_pending_batch_failure_leaves_documents_unembedded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inference = FakeInferenceService()
    inference.fail_batch = True
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("un doc")
    count = svc.vectorize_pending()
    assert count == 0
    assert svc.stats()["embedded"] == 0


def test_vectorize_pending_processes_multiple_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """batch_size est figé à 32 dans _embed_pending : 33 docs => 2 appels embed_batch."""
    inference = FakeInferenceService(default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    for i in range(33):
        svc.index(f"doc-{i}")
    count = svc.vectorize_pending()
    assert count == 33
    assert len(inference.batch_calls) == 2
    assert len(inference.batch_calls[0]) == 32
    assert len(inference.batch_calls[1]) == 1


def test_vectorize_pending_appends_to_already_built_matrix_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()
    svc.search("a", top_k=1)  # construit le matrix cache

    inference.embeddings["b"] = [0.0, 1.0]
    svc.index("b")
    svc.vectorize_pending()  # doit enrichir le matrix cache existant (_append_to_matrix_cache)

    results = svc.search("b", top_k=2)
    assert any(r["text"] == "b" for r in results)


# ---------------------------------------------------------------------------
# index_message() / ingest_message()
# ---------------------------------------------------------------------------


def test_index_message_skips_empty_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "   ", ts=1.0)
    assert svc.stats()["total"] == 0


def test_index_message_adds_new_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "un message", ts=1.0)
    assert svc.stats()["total"] == 1
    assert svc._dirty is True


def test_index_message_dedupes_same_conv_and_msg_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "un message", ts=1.0)
    svc.index_message("c1", "m1", "user", "un message modifié", ts=2.0)
    assert svc.stats()["total"] == 1


def test_ingest_message_indexes_and_embeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.ingest_message("c1", "m1", "user", "un message", ts=1.0)
    assert svc.stats()["total"] == 1
    assert svc.stats()["embedded"] == 1


# ---------------------------------------------------------------------------
# adjust_weight()
# ---------------------------------------------------------------------------


class FakeConversations:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        return {"messages": self._messages}


def test_adjust_weight_updates_matching_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "msg", ts=1.0)
    count = svc.adjust_weight("c1", "m1", delta=0.5)
    assert count == 1
    doc = svc._data["documents"][0]
    assert doc["metadata"]["weight"] == pytest.approx(1.5)


def test_adjust_weight_no_match_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    count = svc.adjust_weight("c1", "inconnu", delta=0.5)
    assert count == 0


def test_adjust_weight_clamps_to_bounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "msg", ts=1.0)
    svc.adjust_weight("c1", "m1", delta=999.0)
    doc = svc._data["documents"][0]
    assert doc["metadata"]["weight"] == WEIGHT_MAX

    svc.adjust_weight("c1", "m1", delta=-999.0)
    assert svc._data["documents"][0]["metadata"]["weight"] == WEIGHT_MIN


def test_adjust_weight_also_updates_preceding_user_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "u1", "user", "question", ts=1.0)
    svc.index_message("c1", "a1", "assistant", "réponse", ts=2.0)
    conversations = FakeConversations([{"id": "u1"}, {"id": "a1"}])

    count = svc.adjust_weight("c1", "a1", delta=1.0, conversations=conversations)
    assert count == 2
    docs_by_msg = {d["metadata"]["msg_id"]: d for d in svc._data["documents"]}
    assert docs_by_msg["a1"]["metadata"]["weight"] == pytest.approx(2.0)
    assert docs_by_msg["u1"]["metadata"]["weight"] == pytest.approx(1.5)  # delta*0.5


def test_adjust_weight_without_conversations_skips_preceding_logic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "u1", "user", "question", ts=1.0)
    svc.index_message("c1", "a1", "assistant", "réponse", ts=2.0)
    count = svc.adjust_weight("c1", "a1", delta=1.0)  # conversations=None (défaut)
    assert count == 1


# ---------------------------------------------------------------------------
# update_score()
# ---------------------------------------------------------------------------


def test_update_score_positive_delta_does_not_increment_bad_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("doc", metadata={"chunk_id": "chunk-1"})
    count = svc.update_score("chunk-1", delta=1.0)
    assert count == 1
    meta = svc._data["documents"][0]["metadata"]
    assert meta["score"] == pytest.approx(1.0)
    assert meta.get("bad_count", 0) == 0


def test_update_score_negative_delta_increments_bad_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("doc", metadata={"chunk_id": "chunk-1", "bad_count": 1})
    count = svc.update_score("chunk-1", delta=-1.0)
    assert count == 1
    meta = svc._data["documents"][0]["metadata"]
    assert meta["score"] == pytest.approx(-1.0)
    assert meta["bad_count"] == 2


def test_update_score_no_match_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    count = svc.update_score("inconnu", delta=-1.0)
    assert count == 0


# ---------------------------------------------------------------------------
# consolidate()
# ---------------------------------------------------------------------------


def test_consolidate_merges_near_duplicate_embeddings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc._data["documents"] = [
        {"text": "a", "metadata": {"weight": 1.0}, "embedding": [1.0, 0.0]},
        {"text": "a-bis", "metadata": {"weight": 2.0}, "embedding": [1.0, 0.0001]},
    ]
    svc.consolidate()
    assert len(svc._data["documents"]) == 1
    assert svc._data["documents"][0]["metadata"]["weight"] == 2.0  # max des deux poids


def test_consolidate_prunes_old_light_conversation_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    old_ts = svc._now() - (CONSOLIDATE_GRACE_HOURS + 1) * 3600
    svc._data["documents"] = [
        {
            "text": "vieux souvenir léger",
            "metadata": {
                "source": "conversation",
                "weight": CONSOLIDATE_PRUNE_WEIGHT,
                "created_at": old_ts,
            },
            "embedding": None,
        },
        {
            "text": "souvenir gardé",
            "metadata": {"source": "conversation", "weight": 1.0, "created_at": svc._now()},
            "embedding": None,
        },
    ]
    svc.consolidate()
    remaining_texts = {d["text"] for d in svc._data["documents"]}
    assert remaining_texts == {"souvenir gardé"}


def test_consolidate_prunes_toxic_chunks_by_bad_count_or_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc._data["documents"] = [
        {
            "text": "toxique par bad_count",
            "metadata": {"bad_count": BAD_COUNT_PRUNING_THRESHOLD + 1, "score": 0.0},
            "embedding": None,
        },
        {
            "text": "toxique par score",
            "metadata": {"bad_count": 0, "score": SCORE_PRUNING_THRESHOLD - 1},
            "embedding": None,
        },
        {"text": "sain", "metadata": {"bad_count": 0, "score": 0.0}, "embedding": None},
    ]
    svc.consolidate()
    remaining_texts = {d["text"] for d in svc._data["documents"]}
    assert remaining_texts == {"sain"}


def test_consolidate_updates_bookkeeping_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("doc")
    svc.consolidate()
    assert svc._data["last_consolidation"] is not None
    assert svc._data["consolidation_runs"] == 1
    svc.consolidate()
    assert svc._data["consolidation_runs"] == 2


def test_consolidate_truncates_index_beyond_max_vector_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    now = svc._now()
    svc._data["documents"] = [
        {
            "text": f"doc-{i}",
            "metadata": {"bad_count": 0, "score": 0.0, "weight": float(i), "created_at": now},
            "embedding": None,
        }
        for i in range(MAX_VECTOR_DOCS + 1)
    ]
    svc.consolidate()
    assert len(svc._data["documents"]) == MAX_VECTOR_DOCS
    # Les poids les plus faibles (created en premier, weight=0.0) sont écartés en priorité.
    kept_weights = {d["metadata"]["weight"] for d in svc._data["documents"]}
    assert 0.0 not in kept_weights


# ---------------------------------------------------------------------------
# clear_cache() / _clear_search_cache() / _get_matrix()
# ---------------------------------------------------------------------------


def test_clear_cache_empties_both_search_and_matrix_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()
    svc.search("a", top_k=1)
    assert svc._matrix_cache.get() is not None

    svc.clear_cache()
    assert svc._matrix_cache.get() is None


def test_get_matrix_reuses_cache_without_rebuilding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()

    calls = []
    original = vector_module.build_normalized_matrix

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(vector_module, "build_normalized_matrix", _spy)
    svc.search("a", top_k=1)
    svc.search("a", top_k=1)  # cache résultat -> ne repasse pas par search() interne
    svc._run_bounded_search("a", np.array([1.0, 0.0], dtype=np.float32), top_k=1, now=svc._now())
    assert len(calls) == 1  # matrice construite une seule fois, réutilisée ensuite


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


def test_search_empty_query_returns_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    assert svc.search("", top_k=5) == []


def test_search_no_documents_returns_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    assert svc.search("une requête", top_k=5) == []


def test_search_embedding_failure_returns_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("un doc")
    svc.vectorize_pending()
    inference.fail_embed_on.add("requête cassée")
    assert svc.search("requête cassée", top_k=5) == []


def test_search_returns_ranked_results_by_cosine_similarity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(
        embeddings={
            "proche": [1.0, 0.0],
            "loin": [0.6, 0.8],
            "hors-seuil": [0.0, 1.0],
            "q": [0.9, 0.1],
        },
        default_dim=2,
    )
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("proche")
    svc.index("loin")
    svc.index("hors-seuil")
    svc.vectorize_pending()

    results = svc.search("q", top_k=3)
    # MT-KB-L2x : seuil 0.5 — "hors-seuil" (cosinus 0.1) est exclu, l'ordre par cosinus est conservé.
    assert [r["text"] for r in results] == ["proche", "loin"]


def test_search_uses_cache_on_second_identical_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()

    svc.search("a", top_k=1)
    calls_before = len(inference.embed_calls)
    svc.search("a", top_k=1)
    assert len(inference.embed_calls) == calls_before  # pas de recalcul d'embedding


def test_search_respects_top_k(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(
        embeddings={"a": [1.0, 0.0], "b": [0.9, 0.1], "c": [0.8, 0.2], "q": [1.0, 0.0]}, default_dim=2
    )
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    for t in ("a", "b", "c"):
        svc.index(t)
    svc.vectorize_pending()

    results = svc.search("q", top_k=2)
    assert len(results) == 2


def test_search_bounded_retry_exhausts_attempts_when_too_few_valid_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Moins de documents valides que top_k : les 3 tentatives de relance
    élargissent la borne sans jamais atteindre top_k, puis abandonnent avec
    un warning explicite (comportement réel, pas un bug corrigé ici)."""
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0], "q": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()

    with caplog.at_level("WARNING", logger="jarvis.vector"):
        results = svc.search("q", top_k=5)
    assert len(results) == 1  # un seul document valide disponible
    assert any("relance non bornée" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------


def test_stats_reports_totals_and_embedding_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.index("b")
    svc.vectorize_pending()  # "a" a un embedding défini, "b" aussi (default_dim fallback)

    stats = svc.stats()
    assert stats["total"] == 2
    assert stats["embedded"] == 2
    assert stats["pending"] == 0
    assert stats["embedding_dim"] == vector_module.EXPECTED_DIM
    assert stats["embedding_model"] == vector_module.EXPECTED_MODEL
    assert stats["migration_status"] == vector_module.MIGRATION_OK
    assert stats["consolidation_runs"] == 0
    assert stats["last_consolidation"] is None


def test_stats_reports_cache_hit_rate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = FakeInferenceService(embeddings={"a": [1.0, 0.0]}, default_dim=2)
    svc = _make_service(monkeypatch, tmp_path, inference=inference)
    svc.index("a")
    svc.vectorize_pending()
    svc.search("a", top_k=1)  # miss
    svc.search("a", top_k=1)  # hit

    stats = svc.stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert stats["cache_hit_rate"] == pytest.approx(50.0)


def test_stats_computes_conversation_weight_mean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index_message("c1", "m1", "user", "msg1", ts=1.0)
    svc.index_message("c1", "m2", "user", "msg2", ts=2.0)
    svc.adjust_weight("c1", "m2", delta=-2.0)  # weight passe de 1.0 à -1.0

    stats = svc.stats()
    assert stats["conversation_docs"] == 2
    assert stats["weight_mean"] == pytest.approx(0.0)  # (1.0 + -1.0) / 2
    assert stats["low_weight_ratio"] == pytest.approx(0.5)  # 1/2 poids <= 0


# ---------------------------------------------------------------------------
# is_healthy()
# ---------------------------------------------------------------------------


def test_is_healthy_true_when_file_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    os.remove(vector_module.VECTOR_PATH) if os.path.exists(vector_module.VECTOR_PATH) else None
    assert svc.is_healthy() is True


def test_is_healthy_true_when_file_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("un doc")
    assert svc.is_healthy() is True


def test_is_healthy_false_when_file_corrupted_after_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _make_service(monkeypatch, tmp_path)
    svc.index("un doc")
    with open(vector_module.VECTOR_PATH, "wb") as f:
        f.write(b"pas du json valide")
    assert svc.is_healthy() is False
