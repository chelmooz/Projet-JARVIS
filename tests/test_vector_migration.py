"""Tests de migration de dimension de l'index vectoriel (AUDIT-P3.1).

Vérifie que VectorService détecte un changement de dimension d'embedding
(stockée vs dimension courante attendue) et déclenche un re-index ou un
reset propre sans crash.
"""
from services.vector import EXPECTED_DIM, VectorService


class TestVectorDimensionMigration:

    def test_stocke_dimension_apres_index(self, tmp_path, monkeypatch):
        # On redirige l'index vectoriel vers un fichier temporaire isolé.
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr("services.vector.VECTOR_PATH", str(index))

        v = VectorService()
        v.index("document alpha", {"src": "test"})
        v.vectorize_pending()

        # La dimension attendue (EXPECTED_DIM) doit être enregistrée dans le store.
        assert v._data.get("embedding_dim") == EXPECTED_DIM
        assert v._data.get("embedding_model") == "nomic-embed-text-v2-moe"
        # Et persistée sur disque.
        import json
        on_disk = json.loads(index.read_text())
        assert on_disk["embedding_dim"] == EXPECTED_DIM

    def test_detecte_mismatch_et_reindexe_sans_crash(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr("services.vector.VECTOR_PATH", str(index))

        # 1) Index initial avec la dimension courante (768).
        v1 = VectorService()
        v1.index("texte conservé", {"src": "mig"})
        v1.vectorize_pending()
        assert v1._data["embedding_dim"] == EXPECTED_DIM

        # 2) Simulation d'un changement de modèle : la dimension attendue devient 512.
        monkeypatch.setattr(
            "services.vector.VectorService._resolve_expected_dim",
            lambda self: 512,
        )
        # Le nouvel embed renvoie bien une dimension de 512 (mock).
        monkeypatch.setattr(
            VectorService, "_embed",
            lambda self, text: [0.0] * 512,
        )

        v2 = VectorService()  # init -> doit détecter le mismatch
        # Le mismatch a été détecté et la migration planifiée (re-index possible).
        assert v2.last_migration in ("reindexed", "reset")
        # Les documents (texte) sont conservés pour permettre le re-index.
        texts = [d["text"] for d in v2._data["documents"]]
        assert "texte conservé" in texts
        # La dimension cible a bien été mise à jour.
        assert v2._data["embedding_dim"] == 512

        # 3) Re-index effectif sans crash.
        count = v2.vectorize_pending()
        assert count == 1
        assert len(v2._data["documents"][0]["embedding"]) == 512
        # Le re-index a bien eu lieu (embeddings recalculés).
        assert v2.last_migration == "reindexed"

    def test_mismatch_sans_texte_reset_propre(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr("services.vector.VECTOR_PATH", str(index))

        # On écrit un index orphelin : dimension 768 mais aucun document texte.
        import json
        index.write_text(json.dumps({
            "documents": [],
            "embeddings": [],
            "embedding_dim": 768,
            "embedding_model": "nomic-embed-text-v2-moe",
        }))

        monkeypatch.setattr(
            "services.vector.VectorService._resolve_expected_dim",
            lambda self: 1024,
        )
        v = VectorService()
        # Pas de texte à re-indexer -> reset propre.
        assert v.last_migration == "reset"
        assert v._data["embedding_dim"] == 1024
        assert v._data["documents"] == []
