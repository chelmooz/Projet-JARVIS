"""MT-KB-L1d — Ingest de 15 entrées MITRE ATT&CK + log (script temporaire, non commité)."""

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
        for _ in range(15):
            line = fh.readline()
            if not line:
                break
            entries.append(json.loads(line))

    service = WikiIngestService()
    paths = service.ingest_batch(entries, max_entries=15)
    service.log_ingest(SOURCE.name, len(paths), paths)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()