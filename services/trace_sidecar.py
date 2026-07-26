import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from services.adapters.protocols import TraceRecord

DATE_FORMAT = "%Y-%m-%d"


class JsonlTraceStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def append(self, record: TraceRecord) -> None:
        filepath = self._build_filepath()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(self._clean(record))
        with filepath.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _build_filepath(self) -> Path:
        today = datetime.now().strftime(DATE_FORMAT)
        return self._base_dir / "traces" / "pipelines" / f"{today}.jsonl"

    def _clean(self, record: TraceRecord) -> dict:
        return {k: v for k, v in asdict(record).items() if v is not None}
