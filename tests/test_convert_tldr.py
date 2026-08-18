"""Tests MT-KB-L3f — convertisseur tldr-pages → JSONL @hardware.

Vérifie le schéma JSONL unifié (5 clés exactes), la normalisation de l'agent
(@hardware), la licence MIT et l'unicité des ids (id = ``tldr/<cmd>``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.convert_tldr_run import convert_tldr_page, convert_tldr_tree

PAGE_TASKSET = """# taskset

> Get or set a process' CPU affinity.

- Get affinity by PID:

`taskset -p {{pid}}`
"""

PAGE_KILL = """# kill

> Sends a signal to a process.

- Terminate a program:

`kill {{pid}}`
"""

PAGE_TOP = """# top

> Display dynamic real-time information about running processes.

- Start top:

`top`
"""


def _write_page(tmp_path: Path, platform: str, name: str, content: str) -> Path:
    pages = tmp_path / "pages" / platform
    pages.mkdir(parents=True, exist_ok=True)
    path = pages / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestTldrConverter:
    def test_page_converts_to_valid_jsonl_entry(self, tmp_path: Path) -> None:
        """Schéma 5 clés exactes, agent @hardware, licence MIT, id tldr/<cmd>."""
        path = _write_page(tmp_path, "linux", "taskset", PAGE_TASKSET)

        entry = convert_tldr_page(path, "linux")

        assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}
        assert entry["id"] == "tldr/taskset"
        assert entry["agent"] == "@hardware"
        assert entry["source"] == "tldr-pages"
        assert entry["text"] == PAGE_TASKSET
        assert entry["metadata"]["agent"] == "@hardware"
        assert entry["metadata"]["source"] == "tldr"
        assert entry["metadata"]["license"] == "MIT"
        assert entry["metadata"]["platform"] == "linux"

    def test_tree_produces_unique_ids_and_guarantees_targets(self, tmp_path: Path) -> None:
        """Id uniques, commandes cibles présentes, cap respecté, pas de doublon."""
        _write_page(tmp_path, "linux", "taskset", PAGE_TASKSET)
        _write_page(tmp_path, "common", "kill", PAGE_KILL)
        _write_page(tmp_path, "common", "top", PAGE_TOP)

        entries = convert_tldr_tree(tmp_path / "pages", limit=2)

        ids = [e["id"] for e in entries]
        assert len(ids) == len(set(ids)), f"ids dupliqués: {ids}"
        assert len(entries) <= 2
        assert all(e["agent"] == "@hardware" for e in entries)
        assert all(e["metadata"]["license"] == "MIT" for e in entries)
