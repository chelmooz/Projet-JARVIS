"""MT-KB-L1b — Ingest de validation des 3 premières entrées MITRE ATT&CK (script temporaire, non commité)."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.wiki_ingest_service import WikiIngestService  # noqa: E402

SOURCE = Path("wiki/sources/mitre-attack.jsonl")


def main() -> None:
    entries = []
    with SOURCE.open(encoding="utf-8") as fh:
        for _ in range(3):
            entries.append(json.loads(fh.readline()))

    service = WikiIngestService()
    paths = service.ingest_batch(entries, max_entries=3)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()