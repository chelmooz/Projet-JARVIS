"""Tests pour le script de reconstruction de l'index (MT-KB-L2n v2).

Couvre la fonction `missing_sources` qui détecte les sources JSONL manquantes
dans l'index par comparaison `metadata.source` (résolue via SOURCE_MAP).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import de la fonction à tester (sera créée dans scripts/rebuild_index_run.py)
# Note: import différé pour éviter l'import du script complet lors de la collecte


def _import_missing_sources():
    """Import lazy de la fonction à tester."""
    import sys
    from pathlib import Path

    # Le script sera dans H:\Projet-JARVIS\scripts
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from scripts.rebuild_index_run import missing_sources

    return missing_sources


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
    index_docs = []

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
