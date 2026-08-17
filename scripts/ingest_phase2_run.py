#!/usr/bin/env python3
"""Script temporaire MT-KB-L2d : ingestion Phase 2 (non commité)."""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.wiki_ingest_service import WikiIngestService
from services.inference import InferenceService


def main() -> int:
    """Point d'entrée principal."""
    print("=== Ingestion Phase 2 : ad-attacks-network + multios-commands ===")

    # Initialiser le service d'inférence (Ollama)
    inference = InferenceService()

    # Initialiser le service d'ingestion
    service = WikiIngestService()

    # Lancer l'ingestion Phase 2
    stats = service.ingest_phase2(inference)

    print(f"Ingested: {stats['ingested']} entries, {stats['chunks']} chunks, {stats['edges']} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())