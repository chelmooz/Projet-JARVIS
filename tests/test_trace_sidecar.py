import json
from datetime import datetime
from pathlib import Path

from services.adapters.protocols import TraceRecord
from services.trace_sidecar import JsonlTraceStore


def test_jsonl_trace_store_appends_record(tmp_path: Path):
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

    store.append(record)

    assert expected_file.exists(), "Le fichier JSONL quotidien n'a pas été créé"

    lines = expected_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "Une seule ligne doit être ajoutée"

    data = json.loads(lines[0])
    assert data["trace_id"] == "trace-123"
    assert data["feedback"] == "👍"


def test_jsonl_trace_store_appends_multiple_records(tmp_path: Path):
    store = JsonlTraceStore(tmp_path)

    record_1 = TraceRecord(
        trace_id="trace-001",
        pipeline_id="diag-reseau",
        query="Perte de paquet",
        retrieved_chunk_ids=["chunk-1"],
        judge_score=0.85,
        judge_reason="Bon diagnostic",
        feedback="👍"
    )
    record_2 = TraceRecord(
        trace_id="trace-002",
        pipeline_id="diag-dns",
        query="Resolution DNS lente",
        retrieved_chunk_ids=["chunk-2"],
        judge_score=0.60,
        judge_reason="Partiel",
        feedback="👎"
    )

    today = datetime.now().strftime("%Y-%m-%d")
    expected_file = tmp_path / "traces" / "pipelines" / f"{today}.jsonl"

    store.append(record_1)
    store.append(record_2)

    lines = expected_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "2 appels append() doivent produire 2 lignes"

    data_1 = json.loads(lines[0])
    assert data_1["trace_id"] == "trace-001"
    assert data_1["feedback"] == "👍"

    data_2 = json.loads(lines[1])
    assert data_2["trace_id"] == "trace-002"
    assert data_2["feedback"] == "👎"
