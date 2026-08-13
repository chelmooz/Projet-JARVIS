from services.vector_dimension import (
    MIGRATION_OK,
    MIGRATION_REINDEXED,
    MIGRATION_RESET,
    DimensionManager,
)


def test_ensure_dimension_init_when_none() -> None:
    data: dict = {}
    dm = DimensionManager(data)
    assert dm.ensure_dimension(8, "model-a") == MIGRATION_OK
    assert data["embedding_dim"] == 8
    assert data["embedding_model"] == "model-a"


def test_ensure_dimension_matching() -> None:
    data = {"embedding_dim": 8, "embedding_model": "model-a"}
    dm = DimensionManager(data)
    assert dm.ensure_dimension(8, "model-a") == MIGRATION_OK


def test_ensure_dimension_reindex_when_texts() -> None:
    data = {
        "embedding_dim": 4,
        "embedding_model": "model-old",
        "documents": [{"text": "hello", "embedding": [1, 2, 3, 4]}],
    }
    dm = DimensionManager(data)
    assert dm.ensure_dimension(8, "model-new") == MIGRATION_REINDEXED
    assert data["embedding_dim"] == 8
    assert data["embedding_model"] == "model-new"
    assert data["documents"][0]["embedding"] is None


def test_ensure_dimension_reset_when_no_texts() -> None:
    data = {
        "embedding_dim": 4,
        "embedding_model": "model-old",
        "documents": [{"embedding": [1, 2, 3, 4]}],
    }
    dm = DimensionManager(data)
    assert dm.ensure_dimension(8, "model-new") == MIGRATION_RESET
    assert data["documents"] == []
    assert data["embedding_dim"] == 8
