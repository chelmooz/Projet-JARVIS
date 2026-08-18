#!/usr/bin/env python3
"""Reconstruction complète de l'index vectoriel (MT-KB-L2n v2).

Reconstruit l'index en une seule commande :
(a) Ingère uniquement les JSONL manquants (détection par metadata.source)
(b) Vectorise les embeddings en attente (embed_batch)
(c) Affiche les stats AVANT/APRÈS total/embedded/pending

Fail-open propre si Ollama indisponible : message clair, index inchangé.
"""

from __future__ import annotations

import json
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


def _resolve_source_from_file(path: Path) -> str | None:
    """Lit la source HF réelle (champ `metadata.source`) depuis la 1re ligne du JSONL."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                src = entry.get("metadata", {}).get("source") if isinstance(entry, dict) else None
                if src:
                    return str(src)
                # Repli : source déjà au niveau racine
                if isinstance(entry, dict) and entry.get("source"):
                    return str(entry["source"])
                break
    except (OSError, json.JSONDecodeError):
        return None
    return None


def missing_sources(sources_dir: Path, index_docs: list[dict[str, Any]]) -> list[str]:
    """
    Retourne la liste des noms de sources JSONL présentes dans `sources_dir`
    mais absentes de l'index (comparaison par `metadata.source` réel lu dans
    le fichier, et non limitée à SOURCE_MAP — ingest toutes les sources disque).

    Args:
        sources_dir: Répertoire contenant les fichiers *.jsonl sources.
        index_docs: Liste des documents de l'index (chaque doc a `metadata.source`).

    Returns:
        Liste des noms de sources (sans extension .jsonl) manquantes dans l'index.
    """
    if not sources_dir.is_dir():
        return []

    # Sources déjà présentes dans l'index
    indexed_sources = {doc.get("metadata", {}).get("source") for doc in index_docs}
    indexed_sources.discard(None)

    # Toutes les sources disque (résolues via le fichier lui-même)
    missing: list[str] = []
    for p in sorted(sources_dir.glob("*.jsonl")):
        if p.stem == "coco-annotations":
            continue  # SKIP @vision (RapidOCR, pas de dataset RAG)
        real_source = _resolve_source_from_file(p) or _resolve_source(p.stem)
        if real_source not in indexed_sources:
            missing.append(p.stem)

    return missing


# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------


def _print_stats(label: str, stats: dict[str, Any]) -> None:
    print(f"{label}: total={stats['total']} embedded={stats['embedded']} pending={stats['pending']}")


# Schéma strict attendu par wiki_ingest_service.ingest_phase2 (_validate_schema)
_REQUIRED_KEYS = {"id", "agent", "source", "text", "metadata"}


def _ensure_five_key_schema(path: Path) -> None:
    """Réécrit un JSONL source en schéma strict 5 clés si besoin (idempotent).

    Certains convertisseurs (convert_hf_sources_run.py) produisent un schéma
    ``{"text", "metadata"}`` à 2 clés, rejeté par ``ingest_phase2``. On promut
    ``id``/``agent``/``source`` (présents dans ``metadata``) au niveau racine.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
    except OSError:
        return

    needs_fix = False
    out: list[str] = []
    for ln in lines:
        try:
            entry = json.loads(ln)
        except json.JSONDecodeError:
            out.append(ln)
            continue
        if isinstance(entry, dict) and set(entry.keys()) == _REQUIRED_KEYS:
            out.append(ln)  # déjà conforme
            continue
        meta = entry.get("metadata", {}) if isinstance(entry, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        new_entry = {
            "id": meta.get("id", entry.get("id", "")),
            "agent": str(meta.get("agent", entry.get("agent", ""))),
            "source": meta.get("source", entry.get("source", "")),
            "text": entry.get("text", ""),
            "metadata": meta,
        }
        out.append(json.dumps(new_entry, ensure_ascii=False))
        needs_fix = True

    if needs_fix:
        with path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"  Schéma normalisé (5 clés) : {path.name}")


def _normalize_index_agents(vector_store: Any) -> int:
    """Force le préfixe '@' sur tous les ``metadata.agent`` de l'index en mémoire.

    Corrige l'incohérence historique (``dev``/``hardware``/``cyber`` sans '@').
    Ne touche pas les valeurs déjà préfixées ni les valeurs non-agent (None).
    """
    docs = vector_store._data.get("documents") if hasattr(vector_store, "_data") else None
    if not isinstance(docs, list):
        return 0
    changed = 0
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        meta = doc.get("metadata")
        if not isinstance(meta, dict):
            continue
        agent = meta.get("agent")
        if isinstance(agent, str) and agent and not agent.startswith("@"):
            meta["agent"] = "@" + agent.strip().lstrip("@")
            changed += 1
    if changed:
        vector_store._dirty = True
        vector_store.flush()
    return changed


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

        # Normalise le schéma source (2 clés -> 5 clés) si besoin
        _ensure_five_key_schema(jsonl_path)

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

    # Normalisation stricte des metadata.agent (force '@' pour tous)
    normalized = _normalize_index_agents(vector_store)
    print(f"Agents normalisés (préfixe '@' forcé) : {normalized}")

    # Smoke test rapide
    smoke = vector_store.search("Kerberoasting T1558.003", top_k=1)
    print(f"Smoke test 'Kerberoasting T1558.003' (top_k=1): results={len(smoke)}")
    for r in smoke:
        meta = r.get("metadata", {})
        print(f"  id={meta.get('id')} agent={meta.get('agent')} score={r.get('score')}")

    _print_stats("FINAL", stats_after)
    print("=== Index KB reconstruit avec succès ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
