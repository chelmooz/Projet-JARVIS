#!/usr/bin/env python3
"""Reconstruction complète de l'index vectoriel (MT-KB-L2n v2).

Reconstruit l'index en une seule commande :
(a) Ingère uniquement les JSONL manquants (détection par metadata.source)
(b) Vectorise les embeddings en attente (embed_batch)
(c) Affiche les stats AVANT/APRÈS total/embedded/pending

Fail-open propre si Ollama indisponible : message clair, index inchangé.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire racine au path pour les imports locaux
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from services.inference import InferenceService
from services.vector import VectorService
from services.wiki_ingest_service import WikiIngestService

# ---------------------------------------------------------------------------
# Détection des sources manquantes
# ---------------------------------------------------------------------------

# Mapping explicite : filename stem -> source HF (champ `source` dans le JSONL)
SOURCE_MAP: dict[str, str] = {
    "ad-attacks-network": "AYI-NEDJIMI/ad-attacks-en",
    "coco-annotations": "coco-2017-val",
    "codesearchnet-python": "codesearchnet-v2-python",
    "grid-stability": "uci-grid-stability",
    "mitre-attack": "mitre-attack-v19.1",
    "multios-commands": "Eng-Elias/multios-terminal-commands",
    "network-topology": "snap-as-skitter",
    "psdocs": "powershell-docs",
    "setuptools": "setuptools",
    "tldr": "tldr-pages",
}


def _resolve_source(stem: str) -> str:
    """Résout le nom de fichier stem vers la source HF réelle (champ `source` du JSONL)."""
    return SOURCE_MAP.get(stem, stem)


def missing_sources(sources_dir: Path, index_docs: list[dict[str, Any]]) -> list[str]:
    """
    Retourne la liste des noms de sources JSONL présentes dans `sources_dir`
    mais absentes de l'index (comparaison par `metadata.source` réel).

    Args:
        sources_dir: Répertoire contenant les fichiers *.jsonl sources.
        index_docs: Liste des documents de l'index (chaque doc a `metadata.source`).

    Returns:
        Liste des noms de sources (sans extension .jsonl) manquantes dans l'index.
    """
    if not sources_dir.is_dir():
        return []

    # Sources présentes sur disque (résolues vers source HF réelle)
    disk_sources = set()
    for p in sources_dir.glob("*.jsonl"):
        real_source = _resolve_source(p.stem)
        disk_sources.add(real_source)

    # Sources déjà présentes dans l'index
    indexed_sources = {doc.get("metadata", {}).get("source") for doc in index_docs}
    indexed_sources.discard(None)

    # Sources manquantes = sur disque mais pas dans l'index
    missing = sorted(disk_sources - indexed_sources)
    # Retourner les stems (noms de fichiers) pour l'affichage et l'ingestion
    return sorted([stem for stem, real in SOURCE_MAP.items() if real in missing])


# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------


def _print_stats(label: str, stats: dict[str, Any]) -> None:
    print(f"{label}: total={stats['total']} embedded={stats['embedded']} pending={stats['pending']}")


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------


def main() -> int:
    """Reconstruit l'index KB en une commande."""
    print("=== Reconstruction de l'index vectoriel KB ===")

    # Vérifier Ollama avant d'aller plus loin
    inference = InferenceService()
    if not inference.is_healthy():
        print("ERREUR: Ollama indisponible (127.0.0.1:11436).")
        print("Vérifiez qu'Ollama tourne: `ollama serve`")
        print("L'index n'a pas été modifié.")
        return 1

    # Initialiser les services
    vs = VectorService(inference_service=inference)

    # Stats AVANT
    stats_before = vs.stats()
    _print_stats("AVANT", stats_before)

    # Détecter sources manquantes
    sources_dir = ROOT / "wiki" / "sources"
    missing = missing_sources(sources_dir, vs._data.get("documents", []))

    if not missing:
        print("Aucune source manquante — index déjà à jour.")
        _print_stats("APRÈS", vs.stats())
        return 0

    print(f"Sources manquantes détectées: {', '.join(missing)}")

    # Ingestion des sources manquantes
    inference_svc = InferenceService()
    vector_store = VectorService(inference_service=inference_svc)
    service = WikiIngestService()

    total_ingested = 0
    total_chunks = 0
    total_edges = 0

    for source in missing:
        jsonl_path = ROOT / "wiki" / "sources" / f"{source}.jsonl"
        if not jsonl_path.is_file():
            print(f"ATTENTION: {jsonl_path} introuvable, ignoré.")
            continue

        # Skip @vision sources (ADR-010: vision=RapidOCR, pas de dataset RAG)
        if source == "coco-annotations":
            print(f"SKIP {source}: agent=@vision (RapidOCR, pas de dataset RAG)")
            continue

        print(f"Ingestion de {source}...")
        stats = service.ingest_phase2(
            inference_svc,
            files=[f"{source}.jsonl"],
            vector_store=vector_store,
            limit=None,
            resume=False,
            progress_every=50,
        )
        total_ingested += stats["ingested"]
        total_chunks += stats["chunks"]
        total_edges += stats["edges"]
        print(f"  {source}: {stats['ingested']} entrées, {stats['chunks']} chunks, {stats['edges']} edges")

    print(f"Total ingéré: {total_ingested} entrées, {total_chunks} chunks, {total_edges} edges")

    # Vectorisation
    print("=== Vectorisation des documents en attente ===")
    stats_before = vector_store.stats()
    _print_stats("AVANT vectorisation", stats_before)

    if stats_before["pending"] > 0:
        count = vector_store.vectorize_pending()
        stats_after = vector_store.stats()
        _print_stats("APRÈS vectorisation", stats_after)
        print(f"Vectorisés: {count} documents")
    else:
        print("Rien à vectoriser (pending=0).")
        stats_after = vector_store.stats()
        _print_stats("APRÈS", stats_after)

    # Smoke test rapide
    smoke = vs.search("Kerberoasting T1558.003", top_k=1)
    print(f"Smoke test 'Kerberoasting T1558.003' (top_k=1): results={len(smoke)}")
    for r in smoke:
        meta = r.get("metadata", {})
        print(f"  id={meta.get('id')} agent={meta.get('agent')} score={r.get('score')}")

    print("=== Index KB reconstruit avec succès ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
