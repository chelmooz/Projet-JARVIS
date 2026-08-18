#!/usr/bin/env python3
"""Conversion tldr-pages → wiki/sources/tldr.jsonl (@hardware, licence MIT).

MT-KB-L3f : les pages tldr (common/linux/osx) couvrent les commandes de
diagnostic système (kill, taskset, ps, top, ...) absentes de multios-commands.

Usage:
    python scripts/convert_tldr_run.py <clone_tldr> [--limit N]

Le clone doit être shallow : ``git clone --depth 1 https://github.com/tldr-pages/tldr.git``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent

# Commandes de diagnostic à garantir (test 9 questions @hardware)
TARGET_COMMANDS: frozenset[str] = frozenset(
    {
        "kill",
        "taskset",
        "ps",
        "top",
        "lsof",
        "netstat",
        "ss",
        "free",
        "df",
        "du",
        "iostat",
        "vmstat",
        "uname",
        "lscpu",
        "lsblk",
        "smartctl",
        "systemctl",
        "journalctl",
        "dmesg",
        "pkill",
        "killall",
        "nice",
        "renice",
        "time",
    }
)

PLATFORMS: tuple[str, ...] = ("common", "linux", "osx")

SOURCE_JSONL = "tldr-pages"
SOURCE_META = "tldr"
LICENSE = "MIT"


def convert_tldr_page(path: Path, platform: str) -> dict[str, Any]:
    """Convertit une page tldr markdown en entrée JSONL 5 clés (@hardware)."""
    text = path.read_text(encoding="utf-8")
    metadata = {
        "agent": "@hardware",
        "source": SOURCE_META,
        "license": LICENSE,
        "platform": platform,
    }
    return {
        "id": f"tldr/{path.stem}",
        "agent": "@hardware",
        "source": SOURCE_JSONL,
        "text": text,
        "metadata": metadata,
    }


def convert_tldr_tree(pages_dir: Path, limit: int = 400) -> list[dict[str, Any]]:
    """Convertit les pages common/linux/osx d'un clone tldr (cap ``limit``).

    Les commandes cibles (diagnostic) sont sélectionnées en premier, puis les
    autres pages triées alphabétiquement. Pas de doublon d'id.
    """
    pages: list[tuple[str, Path]] = []
    for platform in PLATFORMS:
        platform_dir = pages_dir / platform
        if not platform_dir.is_dir():
            continue
        pages.extend((platform, p) for p in sorted(platform_dir.glob("*.md")))

    def sort_key(item: tuple[str, Path]) -> tuple[int, str]:
        platform, path = item
        is_target = 0 if path.stem in TARGET_COMMANDS else 1
        order = PLATFORMS.index(platform)
        return is_target, order, path.stem

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for platform, path in sorted(pages, key=sort_key):
        if len(entries) >= limit:
            break
        if path.stem in seen:
            continue
        seen.add(path.stem)
        entries.append(convert_tldr_page(path, platform))
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
    print(f"tldr: AVANT={before} APRÈS={after} ajoutés={len(entries)}")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Convertit tldr-pages en JSONL @hardware")
    parser.add_argument("clone_dir", type=Path, help="Chemin du clone shallow tldr-pages/tldr")
    parser.add_argument("--limit", type=int, default=400, help="Nombre max d'entrées (défaut 400)")
    args = parser.parse_args(argv)

    entries = convert_tldr_tree(args.clone_dir / "pages", limit=args.limit)
    if not entries:
        print("ERREUR: aucune page convertie — vérifiez le chemin du clone.")
        return 1
    write_jsonl(entries, ROOT / "wiki" / "sources" / "tldr.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
