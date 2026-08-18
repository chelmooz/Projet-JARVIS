#!/usr/bin/env python3
"""Pont Prof IA (H:\\chunks_rag) → JSONL JARVIS (wiki/sources).

Transforme les JSON Prof IA en JSONL par agent pour ingestion JARVIS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire racine au path pour les imports locaux
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_logger = logging.getLogger("jarvis.bridge")


# ---------------------------------------------------------------------------
# Mapping métier → agent
# ---------------------------------------------------------------------------

NETWORK_KEYWORDS = (
    "vlan",
    "bgp",
    "ospf",
    "routage",
    "switch",
    "tcp/ip",
    "vpn",
    "wifi",
)

DESIGNER_KEYWORDS = (
    "support",
    "helpdesk",
    "ticket",
)


def map_metier_to_agent(metier: str, text: str, filename: str) -> str:
    """Mappe un métier vers un agent JARVIS selon les règles.

    Args:
        metier: Métier source (AIS, TSSR, DevOps, Transverse, etc.)
        text: Texte du chunk (pour détection mots-clés réseau)
        filename: Nom du fichier source (pour détection mots-clés designer)

    Returns:
        Préfixe agent avec @ (ex: @cyber, @dev, @hardware, @network, @designer, @orchestrateur)
    """
    metier_lower = metier.lower() if metier else ""
    text_lower = text.lower() if text else ""
    filename_lower = filename.lower() if filename else ""

    if metier_lower == "ais":
        return "@cyber"
    if metier_lower == "devops":
        return "@dev"
    if metier_lower == "tssr":
        # Vérifier mots-clés réseau dans le texte
        for kw in NETWORK_KEYWORDS:
            if kw in text_lower:
                return "@network"
        # Vérifier mots-clés designer dans le filename
        for kw in DESIGNER_KEYWORDS:
            if kw in filename_lower:
                return "@designer"
        return "@hardware"
    if metier_lower == "transverse":
        return "@orchestrateur"

    # Défaut
    return "@orchestrateur"


def normalize_text_for_dedup(text: str) -> str:
    """Normalise le texte pour déduplication MD5 (casse + espaces)."""
    if not text:
        return ""
    # Lowercase, collapse whitespace
    return " ".join(text.lower().split())


def compute_md5(text: str) -> str:
    """Calcule le hash MD5 d'un texte normalisé."""
    normalized = normalize_text_for_dedup(text)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Traitement d'un fichier JSON
# ---------------------------------------------------------------------------


def process_json_file(json_path: Path, output_dir: Path) -> dict[str, int]:
    """Traite un fichier JSON Prof IA et écrit les JSONL par agent.

    Args:
        json_path: Chemin vers le fichier JSON source
        output_dir: Répertoire de sortie pour les JSONL

    Returns:
        Dictionnaire agent -> nombre de chunks écrits
    """
    # Skip les fichiers _backup
    if "_backup" in json_path.name.lower():
        return {}

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _logger.warning("JSON corrompu ou illisible %s: %s", json_path.name, e)
        return {}

    # Extraire le métier depuis la racine, sinon du premier chunk
    metier = data.get("source") or data.get("metier")
    if not metier and data.get("chunks"):
        metier = data["chunks"][0].get("metadata", {}).get("metier")

    filename = data.get("filename", json_path.stem)

    # Buffers par agent pour écriture groupée
    agent_buffers: dict[str, list[dict[str, Any]]] = {}
    seen_hashes: set[str] = set()
    counts: dict[str, int] = {}

    for chunk in data.get("chunks", []):
        text = chunk.get("text", "")
        if len(text) < 80:
            continue  # Filtre: chunk >= 80 caractères

        # Déduplication MD5 normalisé
        chunk_hash = compute_md5(text)
        if chunk_hash in seen_hashes:
            continue
        seen_hashes.add(chunk_hash)

        metadata = chunk.get("metadata", {})
        has_code = metadata.get("has_code", False)
        if isinstance(has_code, str):
            has_code = has_code.lower() == "true"

        agent = map_metier_to_agent(metier or "", text, filename)

        entry = {
            "text": text,
            "metadata": {
                "agent": agent,
                "topic": metier or "Transverse",
                "source": filename,
                "difficulty": "intermediate",
                "has_code": has_code,
            },
        }

        if agent not in agent_buffers:
            agent_buffers[agent] = []
            counts[agent] = 0
        agent_buffers[agent].append(entry)
        counts[agent] += 1

    # Écrire les fichiers JSONL par agent
    for agent, entries in agent_buffers.items():
        agent_file = output_dir / f"{agent}.jsonl"
        # Mode append pour accumulation multi-fichiers
        with agent_file.open("a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Pont Prof IA → JSONL JARVIS")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Répertoire source contenant les JSON Prof IA (ex: H:\\chunks_rag)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Répertoire de sortie pour les JSONL par agent (ex: wiki/sources)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limiter le nombre de fichiers JSON traités (0 = illimité)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs verbeux")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    input_dir = args.input_dir
    output_dir = args.output_dir

    if not input_dir.is_dir():
        _logger.error("Répertoire source introuvable: %s", input_dir)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_dir.glob("*.json"))
    if args.limit > 0:
        json_files = json_files[: args.limit]

    _logger.info("Traitement de %d fichier(s) JSON", len(json_files))

    total_counts: dict[str, int] = {}
    processed = 0

    for json_file in json_files:
        counts = process_json_file(json_file, output_dir)
        for agent, count in counts.items():
            total_counts[agent] = total_counts.get(agent, 0) + count
        processed += 1

        if processed % 100 == 0:
            _logger.info("Progression: %d/%d fichiers", processed, len(json_files))

    _logger.info("Terminé. Fichiers traités: %d", processed)
    for agent, count in sorted(total_counts.items()):
        _logger.info("  %s: %d chunks", agent, count)

    # Afficher 3 lignes d'exemple du premier agent non vide
    for agent in sorted(total_counts.keys()):
        agent_file = output_dir / f"{agent}.jsonl"
        if agent_file.exists():
            lines = agent_file.read_text(encoding="utf-8").strip().split("\n")
            _logger.info("Exemple %s (3 premières lignes):", agent)
            for line in lines[:3]:
                _logger.info("  %s", line)
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
""
