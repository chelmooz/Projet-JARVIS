import numpy as np

from services.vector_weighting import WeightConsolidator


def test_apply_weight_found_and_clamp() -> None:
    docs = [{"metadata": {"conv_id": "c1", "msg_id": "m1", "weight": 2.0}}]
    wc = WeightConsolidator(docs)
    assert wc.apply_weight("c1", "m1", 1.0, 0.0, 5.0) == 1
    assert docs[0]["metadata"]["weight"] == 3.0
    assert wc.apply_weight("c1", "m1", 10.0, 0.0, 5.0) == 1
    assert docs[0]["metadata"]["weight"] == 5.0


def test_apply_weight_not_found() -> None:
    wc = WeightConsolidator([])
    assert wc.apply_weight("c1", "mX", 1.0, 0.0, 5.0) == 0


class _FakeConversations:
    def __init__(self, conv: dict | None) -> None:
        self._conv = conv

    def get_conversation(self, _conv_id: str) -> dict | None:
        return self._conv


def test_preceding_user_msg_id() -> None:
    conv = {"messages": [{"id": "a"}, {"id": "b"}]}
    wc = WeightConsolidator([])
    assert wc.preceding_user_msg_id(_FakeConversations(conv), "c", "b") == "a"
    assert wc.preceding_user_msg_id(None, "c", "b") is None
    assert wc.preceding_user_msg_id(_FakeConversations(None), "c", "x") is None
    assert wc.preceding_user_msg_id(_FakeConversations(conv), "c", "a") is None


def test_normalize_zero_vector_safe() -> None:
    wc = WeightConsolidator([])
    z = wc._normalize([0.0, 0.0])
    assert list(z) == [0.0, 0.0]
    v = wc._normalize([3.0, 4.0])
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_dedup_merges_similar() -> None:
    docs = [
        {"embedding": [1.0, 0.0], "metadata": {"weight": 1.0}},
        {"embedding": [1.0, 0.0], "metadata": {"weight": 2.0}},
        {"embedding": [0.0, 1.0], "metadata": {"weight": 1.0}},
    ]
    wc = WeightConsolidator(docs)
    removed = wc.dedup(0.9, 100)
    assert 1 in removed
    assert 2 not in removed
    assert docs[0]["metadata"]["weight"] == 2.0


def test_dedup_max_pairs_zero() -> None:
    docs = [
        {"embedding": [1.0, 0.0], "metadata": {}},
        {"embedding": [1.0, 0.0], "metadata": {}},
    ]
    wc = WeightConsolidator(docs)
    assert wc.dedup(0.9, 0) == set()


def test_dedup_max_pairs_inner_break() -> None:
    docs = [
        {"embedding": [1.0, 0.0], "metadata": {"weight": 1.0}},
        {"embedding": [1.0, 0.0], "metadata": {"weight": 1.0}},
        {"embedding": [1.0, 0.0], "metadata": {"weight": 1.0}},
    ]
    wc = WeightConsolidator(docs)
    removed = wc.dedup(0.9, 1)
    assert len(removed) == 1


def test_dedup_skips_missing_embedding() -> None:
    docs = [
        {"embedding": None, "metadata": {}},
        {"embedding": [1.0, 0.0], "metadata": {}},
    ]
    wc = WeightConsolidator(docs)
    assert wc.dedup(0.9, 100) == set()


def test_prune_removes_old_light_conv() -> None:
    now = 1_000_000.0
    docs = [
        {"metadata": {"source": "conversation", "weight": 0.5, "created_at": now - 100 * 3600}},
        {"metadata": {"source": "conversation", "weight": 0.5, "created_at": now - 1 * 3600}},
        {"metadata": {"source": "memory", "weight": 0.5, "created_at": now - 100 * 3600}},
        {"metadata": {"source": "conversation", "weight": 5.0, "created_at": now - 100 * 3600}},
    ]
    wc = WeightConsolidator(docs)
    kept = wc.prune(1.0, 24.0, now)
    assert len(kept) == 3


def test_score_and_rank_sorts_and_truncates() -> None:
    now = 1_000_000.0
    results = [
        {"score": 0.5, "metadata": {"weight": 1.0, "created_at": now}},
        {"score": 0.5, "metadata": {"weight": 4.0, "created_at": now}},
        {"score": 0.9, "metadata": {}},
    ]
    wc = WeightConsolidator([])
    ranked = wc.score_and_rank(results, top_k=2, now=now)
    assert len(ranked) == 2
    assert float(ranked[0]["score"]) > float(ranked[1]["score"])
    assert float(ranked[0]["score"]) == round(0.5 * 4.0 * 1.0, 4)
