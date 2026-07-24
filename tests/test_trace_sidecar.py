import json
from pathlib import Path
from datetime import datetime

from services.adapters.protocols import TraceRecord
from services.trace_sidecar import JsonlTraceStore

def test_jsonl_trace_store_appends_record(tmp_path: Path):
    # ARRANGE
    store = JsonlTraceStore(tmp_path)
    record = TraceRecord(
        trace_id="trace-123",
        pipeline_id="diag-reseau",
        query="Perte de paquet sur le nœud A",
        retrieved_chunk_ids=["chunk-1", "chunk-4"],
        judge_score=0.85,
        judge_reason="Diagnostic précis et actionnable",
        feedback="👍"
    )
    
    today = datetime.now().strftime("%Y-%m-%d")
    expected_file = tmp_path / "traces" / "pipelines" / f"{today}.jsonl"

    # ACT
    store.append(record)

    # ASSERT
    assert expected_file.exists(), "Le fichier JSONL quotidien n'a pas été créé"
    
    lines = expected_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "Une seule ligne doit être ajoutée"
    
    data = json.loads(lines[0])
    assert data["trace_id"] == "trace-123"
    assert data["feedback"] == "👍"