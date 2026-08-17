#!/usr/bin/env python3
"""Vectorisation des documents en attente d'embedding (904 docs Phase 2, embeddings null).

Utilise la nouvelle délégation ``InferenceService.embed_batch`` (MT-KB-L2i) pour calculer
les embeddings par lots de 32 (cf. ``services/vector.py::_embed_pending``). À exécuter
APRÈS une ingestion (``scripts/ingest_phase2_run.py``) ou APRÈS restauration de l'index.

Ne ré-ingère PAS : les 904 docs restent, seuls les embeddings null sont calculés.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.inference import InferenceService
from services.vector import VectorService


def main() -> int:
    print("=== Vectorisation des documents en attente d'embedding ===")
    inference = InferenceService()
    vs = VectorService(inference_service=inference)

    stats_before = vs.stats()
    print(f"AVANT: total={stats_before['total']} embedded={stats_before['embedded']} pending={stats_before['pending']}")

    if stats_before["pending"] == 0:
        print("Rien à vectoriser (pending=0).")
        return 0

    count = vs.vectorize_pending()

    stats_after = vs.stats()
    print(f"APRES: total={stats_after['total']} embedded={stats_after['embedded']} pending={stats_after['pending']}")
    print(f"Vectorisé: {count} documents")

    smoke = vs.search("Kerberoasting T1558.003", top_k=1)
    print(f"Smoke test 'Kerberoasting T1558.003' (top_k=1): results={len(smoke)}")
    for r in smoke:
        meta = r.get("metadata", {})
        print(f"  id={meta.get('id')} score={r.get('score')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
