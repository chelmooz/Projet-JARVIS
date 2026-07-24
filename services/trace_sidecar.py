import json
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from services.adapters.protocols import TraceRecord

DATE_FORMAT = "%Y-%m-%d"


class JsonlTraceStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def append(self, record: TraceRecord) -> None:
        filepath = self._build_filepath()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(self._clean(record))
        filepath.write_text(line + "\n", encoding="utf-8")

    def _build_filepath(self) -> Path:
        today = datetime.now().strftime(DATE_FORMAT)
        return self._base_dir / "traces" / "pipelines" / f"{today}.jsonl"

    def _clean(self, record: TraceRecord) -> dict:
        return {k: v for k, v in asdict(record).items() if v is not None}