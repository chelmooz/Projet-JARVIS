#!/usr/bin/env python3
"""Script temporaire MT-KB-L2d : ingestion Phase 2 (non commité)."""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.inference import InferenceService
from services.vector import VectorService
from services.wiki_ingest_service import WikiIngestService


def main() -> int:
    """Point d'entrée principal."""
    print("=== Ingestion Phase 2 : ad-attacks-network + multios-commands ===")

    # Initialiser le service d'inférence (Ollama)
    inference = InferenceService()

    # Initialiser le service vectoriel (runtime store = single source of truth)
    vector_store = VectorService(inference_service=inference)

    # Initialiser le service d'ingestion
    service = WikiIngestService()

    # Lancer l'ingestion Phase 2 avec vector_store injecté
    stats = service.ingest_phase2(
        inference,
        vector_store=vector_store,
        limit=None,
        resume=False,
        progress_every=50,
    )

    print(f"Ingested: {stats['ingested']} entries, {stats['chunks']} chunks, {stats['edges']} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
