#!/usr/bin/env python3
"""Conversion pkg_resources (pypa/setuptools) → wiki/sources/setuptools.jsonl (@dev).

MT-KB-L3f : extrait les fonctions top-level de ``pkg_resources/__init__.py``
(signature + docstring + corps) pour documenter l'API legacy de distribution
Python — y compris les ``DeprecationWarning`` (ex: get_distribution).

Usage:
    python scripts/convert_setuptools_run.py <clone_setuptools> [--limit N]

Le clone doit être shallow :
``git clone --depth 1 --branch v81.0.0 https://github.com/pypa/setuptools.git``
(v81.0.0 = dernier tag contenant pkg_resources ; retiré ensuite).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent

SOURCE_JSONL = "setuptools"
SOURCE_META = "setuptools"
LICENSE = "MIT"

_FUNC_RE = re.compile(r"^def (\w+)\(", re.MULTILINE)


def _function_blocks(source: str) -> list[tuple[str, str]]:
    """Retourne ``(nom, bloc)`` pour chaque fonction top-level du fichier."""
    blocks: list[tuple[str, str]] = []
    matches = list(_FUNC_RE.finditer(source))
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        blocks.append((match.group(1), source[start:end].strip()))
    return blocks


def extract_pkg_resources(source_file: Path, limit: int = 200) -> list[dict[str, Any]]:
    """Extrait les fonctions de ``pkg_resources/__init__.py`` en entrées JSONL @dev.

    Seules les fonctions avec docstring sont retenues (contenu documentaire).
    """
    source = source_file.read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, block in _function_blocks(source):
        if len(entries) >= limit:
            break
        if name in seen:
            continue
        if '"""' not in block.split("\n", 1)[-1]:
            continue  # pas de docstring → skip
        seen.add(name)
        text = block if len(block) <= 2000 else block[:2000].rstrip() + " [...]"
        metadata = {
            "agent": "@dev",
            "source": SOURCE_META,
            "license": LICENSE,
            "function": name,
        }
        entries.append(
            {
                "id": f"setuptools/{name}",
                "agent": "@dev",
                "source": SOURCE_JSONL,
                "text": text,
                "metadata": metadata,
            }
        )
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
    print(f"setuptools: AVANT={before} APRÈS={after} ajoutés={len(entries)}")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Convertit pkg_resources en JSONL @dev")
    parser.add_argument("clone_dir", type=Path, help="Chemin du clone shallow pypa/setuptools (tag v81.0.0)")
    parser.add_argument("--limit", type=int, default=200, help="Nombre max d'entrées (défaut 200)")
    args = parser.parse_args(argv)

    source_file = args.clone_dir / "pkg_resources" / "__init__.py"
    if not source_file.is_file():
        print(f"ERREUR: {source_file} introuvable (tag v81.0.0 requis).")
        return 1
    entries = extract_pkg_resources(source_file, limit=args.limit)
    if not entries:
        print("ERREUR: aucune fonction extraite.")
        return 1
    write_jsonl(entries, ROOT / "wiki" / "sources" / "setuptools.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
