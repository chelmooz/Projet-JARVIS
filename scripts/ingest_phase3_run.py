#!/usr/bin/env python3
"""Script MT-KB-L3c : ingestion Phase 3 (codesearchnet + mitre + network-topology)."""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.inference import InferenceService
from services.vector import VectorService
from services.wiki_ingest_service import WikiIngestService

# Mapping source -> agent attendu (pour validation)
SOURCE_MAP = {
    "codesearchnet-python": "@dev",
    "grid-stability": "@hardware",
    "mitre-attack": "@cyber",
    "network-topology": "@network",
    "ad-attacks-network": "@network",
    "multios-commands": "@hardware",
    "vulnerabilities": "@cyber",
    "coco-annotations": "@vision",  # SKIP - RapidOCR, pas de dataset RAG
}


def missing_sources(sources_dir: Path, index_docs: list) -> list[str]:
    """Retourne la liste des sources JSONL non présentes dans l'index."""
    available_sources = set()
    for doc in index_docs:
        meta = doc.get("metadata", {})
        source = meta.get("source", "")
        if source:
            # Extraire le nom de source du format "source:id"
            src = source.split(":")[0] if ":" in source else source
            available_sources.add(src)

    missing = []
    for source_name in SOURCE_MAP:
        if source_name == "coco-annotations":
            continue  # SKIP explicit
        jsonl_file = sources_dir / f"{source_name}.jsonl"
        if jsonl_file.exists() and source_name not in available_sources:
            missing.append(source_name)

    return missing


def main() -> int:
    """Point d'entrée principal."""
    print("=== Ingestion Phase 3 : codesearchnet + mitre + network-topology ===")

    # Initialiser le service d'inférence (Ollama)
    inference = InferenceService()

    # Initialiser le service vectoriel (runtime store = single source of truth)
    vector_store = VectorService(inference_service=inference)

    # Initialiser le service d'ingestion
    service = WikiIngestService()

    # Charger l'index existant pour détecter les sources manquantes
    stats_before = vector_store.stats()
    print(f"AVANT: total={stats_before['total']} embedded={stats_before['embedded']} pending={stats_before['pending']}")

    # Détecter les sources manquantes
    sources_dir = Path("wiki/sources")
    # Accéder aux documents via _data (protégé par lock, mais lecture seule ici)
    index_docs = vector_store._data.get("documents", [])
    missing = missing_sources(sources_dir, index_docs)

    if not missing:
        print("Aucune source manquante à ingérer.")
        return 0

    print(f"Sources manquantes détectées: {missing}")

    # Ingestion sélective des sources manquantes
    for source in missing:
        print(f"\n--- Ingération de {source}.jsonl ---")
        try:
            stats = service.ingest_phase2(
                inference,
                vector_store=vector_store,
                files=[f"{source}.jsonl"],
                limit=None,
                resume=False,
                progress_every=50,
            )
            print(f"  Ingested: {stats['ingested']} entries, {stats['chunks']} chunks, {stats['edges']} edges")
        except ValueError as e:
            print(f"  SKIP: {e}")

    # Vectoriser les documents en attente
    print("\n=== Vectorisation des documents en attente ===")
    stats_before_vec = vector_store.stats()
    print(
        f"AVANT vectorize_pending: total={stats_before_vec['total']} embedded={stats_before_vec['embedded']} pending={stats_before_vec['pending']}"
    )

    if stats_before_vec["pending"] > 0:
        count = vector_store.vectorize_pending()
        stats_after_vec = vector_store.stats()
        print(
            f"APRÈS vectorize_pending: total={stats_after_vec['total']} embedded={stats_after_vec['embedded']} pending={stats_after_vec['pending']}"
        )
        print(f"Vectorisé: {count} documents")
    else:
        print("Rien à vectoriser (pending=0).")

    # Smoke test
    print("\n=== Smoke test ===")
    smoke = vector_store.search("complain(distribution_name)", top_k=1)
    print(f"Smoke test 'complain(distribution_name)' (top_k=1): results={len(smoke)}")
    for r in smoke:
        meta = r.get("metadata", {})
        agent = meta.get("agent", "unknown")
        score = r.get("score", 0)
        print(f"  id={meta.get('id')} agent={agent} score={score}")

    stats_final = vector_store.stats()
    print(f"\nFINAL: total={stats_final['total']} embedded={stats_final['embedded']} pending={stats_final['pending']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
