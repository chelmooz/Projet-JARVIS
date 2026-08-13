from ports import EmbeddingPort, VectorPort


def test_fake_embedding_deterministic(embedding: EmbeddingPort) -> None:
    vec = embedding.embed("hello")
    assert isinstance(vec, list)
    assert all(isinstance(x, float) for x in vec)
    assert vec == embedding.embed("hello")


def test_fake_vector_index_and_search(vector: VectorPort) -> None:
    assert vector.is_healthy()
    vector.index("doc-1", {"src": "a"})
    vector.index("doc-2", {"src": "b"})
    assert vector.vectorize_pending() == 2
    assert vector.stats() == {"count": 2}
    results = vector.search("query", top_k=1)
    assert results[0]["text"] == "doc-1"
    assert results[0]["metadata"] == {"src": "a"}
