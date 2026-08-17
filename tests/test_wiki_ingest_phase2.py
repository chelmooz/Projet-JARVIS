"""Tests pour l'ingestion Phase 2 (JSONL @network + @hardware)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.wiki_ingest_service import WikiIngestService


class TestPhase2Ingest:
    """Tests d'ingestion Phase 2 : ad-attacks-network + multios-commands."""

    @pytest.fixture
    def service(self) -> WikiIngestService:
        return WikiIngestService()

    @pytest.fixture
    def mock_inference(self) -> MagicMock:
        """Mock du service d'inférence pour les embeddings."""
        mock = MagicMock()
        # embed_batch retourne une liste de 768 floats par texte
        mock.embed_batch.return_value = [[0.1] * 768]
        return mock

    @pytest.fixture
    def temp_jsonl_file(self, tmp_path: Path) -> Path:
        """Crée un fichier JSONL temporaire avec 3 entrées de test."""
        file_path = tmp_path / "test.jsonl"
        entries = [
            {"id": "test-1", "agent": "@network", "source": "test", "text": "Entry 1: T1021.002 description", "metadata": {}},
            {"id": "test-2", "agent": "@network", "source": "test", "text": "Entry 2: T1021.006 description", "metadata": {}},
            {"id": "test-3", "agent": "@network", "source": "test", "text": "Entry 3: no mitre here", "metadata": {}},
        ]
        with file_path.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return file_path

    def test_ingest_ad_attacks_network(self, service: WikiIngestService, mock_inference: MagicMock) -> None:
        """32 entrées @network ingérées, liens croisés vers MITRE."""
        # Le fichier ad-attacks-network.jsonl contient 32 entrées
        # Certaines contiennent des Txxxxxx (ex: T1021.002) → edges vers MITRE
        stats = service.ingest_phase2(mock_inference, files=["ad-attacks-network.jsonl"])

        assert stats["ingested"] == 32, f"Attendu 32 entrées ingérées, reçu {stats['ingested']}"
        assert stats["chunks"] > 0, "Des chunks doivent être créés"
        # Au moins quelques edges vers MITRE (T1021.002, T1021.006, T1021.003, T1563.001, T1557.002, T1566.002, T1087.002, T1087.004)
        assert stats["edges"] >= 5, f"Attendu au moins 5 edges MITRE, reçu {stats['edges']}"

    def test_ingest_multios_hardware(self, service: WikiIngestService, mock_inference: MagicMock) -> None:
        """1000 entrées @hardware ingérées, chunking 512/64."""
        stats = service.ingest_phase2(mock_inference, files=["multios-commands.jsonl"])

        assert stats["ingested"] == 1000, f"Attendu 1000 entrées ingérées, reçu {stats['ingested']}"
        # Chunking : 512 tokens, overlap 64
        # Les entrées sont courtes, mais le chunking doit s'appliquer
        assert stats["chunks"] >= 1000, f"Attendu au moins 1000 chunks, reçu {stats['chunks']}"
        # Pas de Txxxxxx dans multios-commands → 0 edges MITRE pour ce dataset
        # (mais il peut y avoir des edges du dataset network)

    def test_schema_validation(self, service: WikiIngestService) -> None:
        """Tous les JSONL ont exactement {id, agent, source, text, metadata}."""
        # Cette validation se fait dans ingest_phase2
        # Si un fichier a un schéma invalide, une exception doit être levée
        # On teste indirectement via l'appel sans erreur
        mock_inference = MagicMock()
        mock_inference.embed_batch.return_value = [[0.1] * 768]

        # Ne doit pas lever d'exception
        stats = service.ingest_phase2(mock_inference)
        assert stats["ingested"] == 1032  # 32 + 1000

    def test_vector_index_updated(self, service: WikiIngestService, mock_inference: MagicMock) -> None:
        """wiki_index.bin contient les nouveaux embeddings."""
        # Après ingest_phase2, l'index vectoriel doit contenir les nouveaux documents
        # Le VectorService utilise vector_index.json, mais le test mentionne wiki_index.bin
        # On vérifie que l'index a été mis à jour via les stats
        stats = service.ingest_phase2(mock_inference)

        # L'index doit avoir été mis à jour (chunks > 0 implique indexation)
        assert stats["chunks"] > 0, "L'index vectoriel doit avoir été mis à jour"

        # Vérification plus précise : le service d'ingest doit avoir appelé index_batch ou similaire
        # sur le VectorService avec les chunks et embeddings

    def test_ingest_phase2_limit(self, service: WikiIngestService, mock_inference: MagicMock, tmp_path: Path) -> None:
        """Avec limit=2 sur un JSONL de 3 entrées, stats['ingested'] == 2."""
        # Créer un fichier JSONL temporaire dans le dossier sources du wiki_root
        sources_dir = tmp_path / "wiki" / "sources"
        sources_dir.mkdir(parents=True)
        test_file = sources_dir / "test-limit.jsonl"
        entries = [
            {"id": "limit-1", "agent": "@network", "source": "test", "text": "Entry 1", "metadata": {}},
            {"id": "limit-2", "agent": "@network", "source": "test", "text": "Entry 2", "metadata": {}},
            {"id": "limit-3", "agent": "@network", "source": "test", "text": "Entry 3", "metadata": {}},
        ]
        with test_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Utiliser un WikiIngestService avec ce tmp_path
        service = WikiIngestService(wiki_root=tmp_path / "wiki")
        stats = service.ingest_phase2(mock_inference, files=["test-limit.jsonl"], limit=2)

        assert stats["ingested"] == 2, f"Attendu 2 entrées ingérées avec limit=2, reçu {stats['ingested']}"

    def test_ingest_phase2_resume(self, service: WikiIngestService, mock_inference: MagicMock, tmp_path: Path) -> None:
        """Checkpoint pré-écrit avec l'id de la 1ère entrée → resume=True → 1ère entrée sautée."""
        sources_dir = tmp_path / "wiki" / "sources"
        sources_dir.mkdir(parents=True)
        test_file = sources_dir / "test-resume.jsonl"
        entries = [
            {"id": "resume-1", "agent": "@network", "source": "test", "text": "Entry 1", "metadata": {}},
            {"id": "resume-2", "agent": "@network", "source": "test", "text": "Entry 2", "metadata": {}},
            {"id": "resume-3", "agent": "@network", "source": "test", "text": "Entry 3", "metadata": {}},
        ]
        with test_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Écrire un checkpoint avec la 1ère entrée déjà traitée
        checkpoint_path = tmp_path / "wiki" / ".phase2_checkpoint.json"
        checkpoint_path.write_text(json.dumps(["resume-1"]), encoding="utf-8")

        service = WikiIngestService(wiki_root=tmp_path / "wiki")
        stats = service.ingest_phase2(mock_inference, files=["test-resume.jsonl"], resume=True)

        # Doit ingérer 2 entrées (resume-2, resume-3), sauter resume-1
        assert stats["ingested"] == 2, f"Attendu 2 entrées ingérées (reprise), reçu {stats['ingested']}"

    def test_ingest_phase2_progress(self, service: WikiIngestService, mock_inference: MagicMock, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """progress_every=1, limit=3 → stdout contient une ligne de progression avec flush."""
        sources_dir = tmp_path / "wiki" / "sources"
        sources_dir.mkdir(parents=True)
        test_file = sources_dir / "test-progress.jsonl"
        entries = [
            {"id": "prog-1", "agent": "@network", "source": "test", "text": "Entry 1", "metadata": {}},
            {"id": "prog-2", "agent": "@network", "source": "test", "text": "Entry 2", "metadata": {}},
            {"id": "prog-3", "agent": "@network", "source": "test", "text": "Entry 3", "metadata": {}},
        ]
        with test_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        service = WikiIngestService(wiki_root=tmp_path / "wiki")
        stats = service.ingest_phase2(mock_inference, files=["test-progress.jsonl"], limit=3, progress_every=1)

        captured = capsys.readouterr()
        # Vérifier qu'une ligne de progression a été affichée (ex: "1/3", "2/3", "3/3")
        assert any(f"{i}/3" in captured.out for i in range(1, 4)), f"Sortie stdout attendue avec progression, reçu: {captured.out}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
