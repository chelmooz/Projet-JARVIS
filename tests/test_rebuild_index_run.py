"""Tests pour le script de reconstruction de l'index (MT-KB-L2n v2).

Couvre la fonction `missing_sources` qui détecte les sources JSONL manquantes
dans l'index par comparaison `metadata.source` (résolue via SOURCE_MAP).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import de la fonction à tester (sera créée dans scripts/rebuild_index_run.py)
# Note: import différé pour éviter l'import du script complet lors de la collecte


def _import_missing_sources() -> Callable[[Path, list[dict[str, Any]]], list[str]]:
    """Import lazy de la fonction à tester."""
    import sys
    from pathlib import Path

    # Le script sera dans H:\Projet-JARVIS\scripts
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from scripts.rebuild_index_run import missing_sources

    return missing_sources


def _import_main() -> Callable[[], int]:
    """Import lazy de la fonction main pour test d'intégration."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from scripts.rebuild_index_run import main

    return main


def test_missing_sources_all_missing(tmp_path: Path) -> None:
    """RED: Quand l'index est vide, toutes les sources sont manquantes."""
    missing_sources = _import_missing_sources()

    # Créer 2 fichiers JSONL sources dans tmp_path
    # Utiliser des noms de sources présents dans SOURCE_MAP (clés = filename stem)
    src_dir = tmp_path / "sources"
    src_dir.mkdir()
    (src_dir / "ad-attacks-network.jsonl").write_text(
        '{"text": "a", "metadata": {"id": "1", "agent": "@cyber", "source": "AYI-NEDJIMI/ad-attacks-en"}}\n'
    )
    (src_dir / "multios-commands.jsonl").write_text(
        '{"text": "b", "metadata": {"id": "2", "agent": "@hardware", "source": "Eng-Elias/multios-terminal-commands"}}\n'
    )

    # Index vide
    index_docs: list[dict[str, Any]] = []

    missing = missing_sources(src_dir, index_docs)
    assert set(missing) == {"ad-attacks-network", "multios-commands"}


def test_missing_sources_none_missing(tmp_path: Path) -> None:
    """RED: Quand l'index contient déjà toutes les sources, rien n'est manquant."""
    missing_sources = _import_missing_sources()

    src_dir = tmp_path / "sources"
    src_dir.mkdir()
    (src_dir / "ad-attacks-network.jsonl").write_text(
        '{"text": "a", "metadata": {"id": "1", "agent": "@cyber", "source": "AYI-NEDJIMI/ad-attacks-en"}}\n'
    )
    (src_dir / "multios-commands.jsonl").write_text(
        '{"text": "b", "metadata": {"id": "2", "agent": "@hardware", "source": "Eng-Elias/multios-terminal-commands"}}\n'
    )

    # Index contient déjà les sources (utilise les vraies valeurs source HF)
    index_docs = [
        {"metadata": {"source": "AYI-NEDJIMI/ad-attacks-en"}},
        {"metadata": {"source": "Eng-Elias/multios-terminal-commands"}},
    ]

    missing = missing_sources(tmp_path / "sources", index_docs)
    assert missing == []


def test_missing_sources_partial_missing(tmp_path: Path) -> None:
    """RED: Cas mixte — une source présente, une manquante."""
    missing_sources = _import_missing_sources()

    src_dir = tmp_path / "sources"
    src_dir.mkdir()
    (src_dir / "ad-attacks-network.jsonl").write_text(
        '{"text": "a", "metadata": {"id": "1", "agent": "@cyber", "source": "AYI-NEDJIMI/ad-attacks-en"}}\n'
    )
    (src_dir / "multios-commands.jsonl").write_text(
        '{"text": "b", "metadata": {"id": "2", "agent": "@hardware", "source": "Eng-Elias/multios-terminal-commands"}}\n'
    )

    index_docs = [{"metadata": {"source": "AYI-NEDJIMI/ad-attacks-en"}}]

    missing = missing_sources(tmp_path / "sources", index_docs)
    assert missing == ["multios-commands"]


def test_vectorize_uses_correct_instance() -> None:
    """RED: Vérifie que vectorize_pending est appelé sur l'instance qui a reçu les nouveaux docs.

    Ce test simule le bug où `vs` (instance initiale) est utilisé au lieu de
    `vector_store` (instance qui a ingéré les nouveaux documents).
    """
    main = _import_main()

    with (
        patch("scripts.rebuild_index_run.InferenceService") as mock_inference,
        patch("scripts.rebuild_index_run.VectorService") as mock_vector_service,
        patch("scripts.rebuild_index_run.WikiIngestService") as mock_ingest_service,
        patch("scripts.rebuild_index_run.missing_sources", return_value=["test-source"]),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
    ):
        # Configuration des mocks
        mock_inference_instance = MagicMock()
        mock_inference_instance.is_healthy.return_value = True
        mock_inference.return_value = mock_inference_instance

        # DEUX instances VectorService distinctes
        mock_vs_initial = MagicMock()
        mock_vs_initial.stats.return_value = {"total": 100, "embedded": 100, "pending": 0}
        mock_vs_initial._data = {"documents": []}

        mock_vector_store = MagicMock()
        mock_vector_store.stats.side_effect = [
            {"total": 100, "embedded": 50, "pending": 50},  # AVANT vectorisation (avec nouveaux docs)
            {"total": 150, "embedded": 150, "pending": 0},  # APRÈS vectorisation
        ]
        mock_vector_store.vectorize_pending.return_value = 50

        # VectorService() appelé 2 fois: 1ère pour vs, 2ème pour vector_store
        mock_vector_service.side_effect = [mock_vs_initial, mock_vector_store]

        mock_ingest_instance = MagicMock()
        mock_ingest_instance.ingest_phase2.return_value = {"ingested": 10, "chunks": 50, "edges": 5}
        mock_ingest_service.return_value = mock_ingest_instance

        # Exécuter main
        result = main()

        # Vérifier que vectorize_pending a été appelé sur vector_store (2ème instance)
        # et PAS sur vs (1ère instance)
        mock_vs_initial.vectorize_pending.assert_not_called()
        mock_vector_store.vectorize_pending.assert_called_once()

        # Vérifier que les stats AVANT/APRÈS vectorisation viennent de vector_store
        assert mock_vector_store.stats.call_count == 2

        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
