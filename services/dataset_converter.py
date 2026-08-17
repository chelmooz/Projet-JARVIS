"""Convertisseurs de datasets vers JSONL (fonctions pures, sans réseau).

Responsabilité unique : transformer des entrées brutes de datasets externes
vers le schéma JSONL unifié JARVIS : {"id", "agent", "source", "text", "metadata"}.

Aucune dépendance réseau ici — le téléchargement se fait dans le script temporaire.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Constantes de filtrage (v1, documentées)
# ---------------------------------------------------------------------------

# Catégories AD considérées "réseau pur" (pas déjà dans MITRE @cyber)
ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "reconnaissance",
        "discovery",
        "lateral_movement",
        "command_and_control",
    }
)

# Outils dont la présence exclut l'entrée même si catégorie autorisée
EXCLUDED_TOOLS: frozenset[str] = frozenset({"Mimikatz", "Rubeus"})


# ---------------------------------------------------------------------------
# Filtre ad-attacks-en
# ---------------------------------------------------------------------------


def filter_ad_attacks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtre les entrées ad-attacks-en selon les règles v1.

    Règles :
    - GARDER si category ∈ ALLOWED_CATEGORIES
    - EXCLURE si category ∉ ALLOWED_CATEGORIES
    - EXCLURE si un outil dans tools ∈ EXCLUDED_TOOLS (même si catégorie autorisée)

    Args:
        entries: Liste d'entrées brutes ad-attacks (attacks.json, tools.json, etc.)

    Returns:
        Liste filtrée (copie, ne modifie pas l'entrée).
    """
    kept: list[dict[str, Any]] = []
    for entry in entries:
        category = entry.get("category", "").lower()
        if category not in ALLOWED_CATEGORIES:
            continue
        tools = entry.get("tools", [])
        if isinstance(tools, list):
            tool_names = {str(t) for t in tools}
            if tool_names & EXCLUDED_TOOLS:
                continue
        kept.append(entry)
    return kept


# ---------------------------------------------------------------------------
# Convertisseurs vers schéma JSONL unifié
# ---------------------------------------------------------------------------


def _make_base_entry(
    *,
    entry_id: str,
    agent: str,
    source: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Construit une entrée JSONL avec les 5 clés requises."""
    return {
        "id": entry_id,
        "agent": agent,
        "source": source,
        "text": text,
        "metadata": metadata,
    }


def convert_ad_attacks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convertit entrées ad-attacks-en filtrées vers schéma JSONL (@network).

    Args:
        entries: Entrées déjà filtrées par filter_ad_attacks().

    Returns:
        Liste d'entrées JSONL prêtes pour écriture.
    """
    converted: list[dict[str, Any]] = []
    for entry in entries:
        entry_id = str(entry.get("id", ""))
        name = entry.get("name", "")
        description = entry.get("description", "")
        text = f"{name}: {description}".strip()
        metadata = {
            "category": entry.get("category", ""),
            "mitre_technique_ids": entry.get("mitre_technique_ids", []),
            "severity": entry.get("severity", ""),
            "prerequisites": entry.get("prerequisites", []),
            "tools": entry.get("tools", []),
            "detection": entry.get("detection", ""),
            "mitigation": entry.get("mitigation", ""),
            "source_url": entry.get("source_url", ""),
        }
        converted.append(
            _make_base_entry(
                entry_id=entry_id,
                agent="@network",
                source="AYI-NEDJIMI/ad-attacks-en",
                text=text,
                metadata=metadata,
            )
        )
    return converted


def convert_multios(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convertit entrées multios-terminal-commands vers schéma JSONL (@hardware).

    Args:
        entries: Entrées brutes du dataset (champs instruction, input, output).

    Returns:
        Liste d'entrées JSONL prêtes pour écriture.
    """
    converted: list[dict[str, Any]] = []
    for entry in entries:
        instruction = entry.get("instruction", "")
        output_raw = entry.get("output", "")
        # Parse output JSON si possible, sinon utilise brut
        try:
            output_parsed = json.loads(output_raw)
            if isinstance(output_parsed, dict):
                # Format multi-plateforme : {"description": "...", "linux": "...", "windows": "...", "mac": "..."}
                windows_cmd = output_parsed.get("windows", "")
                linux_cmd = output_parsed.get("linux", "")
                mac_cmd = output_parsed.get("mac", "")
                text = f"{instruction} → Windows: {windows_cmd}"
                metadata = {
                    "instruction": instruction,
                    "input": entry.get("input", ""),
                    "linux": linux_cmd,
                    "windows": windows_cmd,
                    "mac": mac_cmd,
                }
            else:
                text = f"{instruction} → {output_raw}"
                metadata = {"instruction": instruction, "input": entry.get("input", ""), "output": output_raw}
        except json.JSONDecodeError:
            # output n'est pas du JSON (ex: "echo N/A")
            text = f"{instruction} → {output_raw}"
            metadata = {"instruction": instruction, "input": entry.get("input", ""), "output": output_raw}

        converted.append(
            _make_base_entry(
                entry_id=str(instruction).replace(" ", "_").replace("'", "").lower()[:50],
                agent="@hardware",
                source="Eng-Elias/multios-terminal-commands",
                text=text,
                metadata=metadata,
            )
        )
    return converted


__all__ = [
    "ALLOWED_CATEGORIES",
    "EXCLUDED_TOOLS",
    "filter_ad_attacks",
    "convert_ad_attacks",
    "convert_multios",
]
