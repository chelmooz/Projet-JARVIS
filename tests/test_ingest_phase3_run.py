#!/usr/bin/env python3
"""Tests pour ingest_phase3_run.py — détection des sources manquantes."""

import pytest
from pathlib import Path
from scripts.ingest_phase3_run import missing_sources


class TestIngestPhase3MissingSources:
    """Tests de détection des sources JSONL non ingérées."""

    def test_missing_sources_detects_codesearchnet(self) -> None:
        """Détecte codesearchnet-python.jsonl manquant."""
        # Créer un index factice sans codesearchnet
        index_docs = [{"metadata": {"source": "other-source:doc1"}}]
        sources_dir = Path("wiki/sources")
        
        missing = missing_sources(sources_dir, index_docs)
        
        assert "codesearchnet-python" in missing, f"codesearchnet-python devrait être manquant, got: {missing}"

    def test_missing_sources_detects_mitre(self) -> None:
        """Détecte mitre-attack.jsonl manquant."""
        index_docs = [{"metadata": {"source": "other-source:doc1"}}]
        sources_dir = Path("wiki/sources")
        
        missing = missing_sources(sources_dir, index_docs)
        
        assert "mitre-attack" in missing, f"mitre-attack devrait être manquant, got: {missing}"

    def test_missing_sources_detects_network_topology(self) -> None:
        """Détecte network-topology.jsonl manquant."""
        index_docs = [{"metadata": {"source": "other-source:doc1"}}]
        sources_dir = Path("wiki/sources")
        
        missing = missing_sources(sources_dir, index_docs)
        
        assert "network-topology" in missing, f"network-topology devrait être manquant, got: {missing}"
