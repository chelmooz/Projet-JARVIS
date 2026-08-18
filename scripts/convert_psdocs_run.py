#!/usr/bin/env python3
"""Conversion PowerShell-Docs → wiki/sources/psdocs.jsonl (@hardware + @dev).

MT-KB-L3f : les cmdlets PowerShell de diagnostic système (Get-Process,
Get-CimInstance, Get-Counter, ...) → @hardware ; les autres cmdlets et scripts
(Utility, Security, ...) → @dev.

Usage:
    python scripts/convert_psdocs_run.py <clone_psdocs> [--limit N]

Le clone doit être shallow :
``git clone --depth 1 https://github.com/MicrosoftDocs/PowerShell-Docs.git``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent

# Modules de diagnostic système → @hardware
HARDWARE_MODULES: frozenset[str] = frozenset(
    {
        "CimCmdlets",
        "Microsoft.PowerShell.Diagnostics",
        "PSDiagnostics",
    }
)

# Cmdlets de diagnostic hors modules ci-dessus (Management/Core) → @hardware
HARDWARE_CMDLET_PATTERNS: tuple[str, ...] = (
    "Process",
    "Service",
    "EventLog",
    "Event",
    "Counter",
    "PnpDevice",
    "Computer",
)

SOURCE_JSONL = "powershell-docs"
SOURCE_META = "powershell-docs"
LICENSE = "CC-BY-4.0"


def _is_hardware_cmdlet(name: str, module: str) -> bool:
    if module in HARDWARE_MODULES:
        return True
    return any(pattern in name for pattern in HARDWARE_CMDLET_PATTERNS)


def convert_cmdlet(path: Path, module: str) -> dict[str, Any]:
    """Convertit une page cmdlet markdown en entrée JSONL 5 clés."""
    name = path.stem
    agent = "@hardware" if _is_hardware_cmdlet(name, module) else "@dev"
    text = path.read_text(encoding="utf-8")
    metadata = {
        "agent": agent,
        "source": SOURCE_META,
        "license": LICENSE,
        "module": module,
    }
    return {
        "id": f"psdocs/{name}",
        "agent": agent,
        "source": SOURCE_JSONL,
        "text": text,
        "metadata": metadata,
    }


def convert_psdocs_tree(reference_dir: Path, limit: int = 300) -> list[dict[str, Any]]:
    """Convertit les cmdlets d'un dossier reference/<version> (cap ``limit``).

    Les modules @hardware sont sélectionnés en premier (diagnostic), puis les
    autres modules par ordre alphabétique. Pas de doublon d'id.
    """
    modules: list[Path] = sorted(p for p in reference_dir.iterdir() if p.is_dir())

    def sort_key(module: Path) -> tuple[int, str]:
        return 0 if module.name in HARDWARE_MODULES else 1, module.name

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for module_dir in sorted(modules, key=sort_key):
        for path in sorted(module_dir.glob("*.md")):
            if len(entries) >= limit:
                break
            if path.stem in seen:
                continue
            seen.add(path.stem)
            entries.append(convert_cmdlet(path, module_dir.name))
        if len(entries) >= limit:
            break
    return entries


def write_jsonl(entries: list[dict[str, Any]], out_path: Path) -> int:
    """Valide le schéma 5 clés et écrit le JSONL (compteur AVANT/APRÈS)."""
    required = {"id", "agent", "source", "text", "metadata"}
    before = out_path.read_text(encoding="utf-8").count("\n") if out_path.exists() else 0
    with out_path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            if set(entry.keys()) != required:
                raise ValueError(f"Schéma invalide: {set(entry.keys())} vs {required}")
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    after = out_path.read_text(encoding="utf-8").count("\n") if out_path.exists() else 0
    print(f"psdocs: AVANT={before} APRÈS={after} ajoutés={len(entries)}")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Convertit PowerShell-Docs en JSONL @hardware/@dev")
    parser.add_argument("clone_dir", type=Path, help="Chemin du clone shallow MicrosoftDocs/PowerShell-Docs")
    parser.add_argument("--version", type=str, default="7.4", help="Version de référence (défaut 7.4)")
    parser.add_argument("--limit", type=int, default=300, help="Nombre max d'entrées (défaut 300)")
    args = parser.parse_args(argv)

    reference_dir = args.clone_dir / "reference" / args.version
    if not reference_dir.is_dir():
        print(f"ERREUR: {reference_dir} introuvable.")
        return 1
    entries = convert_psdocs_tree(reference_dir, limit=args.limit)
    if not entries:
        print("ERREUR: aucune cmdlet convertie — vérifiez le chemin du clone.")
        return 1
    write_jsonl(entries, ROOT / "wiki" / "sources" / "psdocs.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
