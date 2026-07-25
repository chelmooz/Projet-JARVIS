"""Benchmark I/O — mesure read_json / write_json_atomic avec stdlib json (baseline).

Ce test établit la baseline P50/P95/P99 AVANT la migration vers orjson.
Il est auto-valide : les assertions vérifient que les opérations réussissent.
Les métriques sont loggées dans ``test_io_perf_results.log`` pour comparaison.
"""

import json
import logging
import os
import statistics
import time

import pytest

import services.file_utils as fu

_logger = logging.getLogger(__name__)
_RESULTS_LOG = os.path.join(os.path.dirname(__file__), "..", "test_io_perf_results.log")
_ITERATIONS = 100
_P50_TOLERANCE_MS = 80.0  # baseline stdlib ; orjson devrait descendre sous 20ms


def _log_result(label: str, latencies: list[float]):
    """Logge les métriques P50/P95/P99 dans un fichier."""
    p50 = statistics.median(latencies)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean = statistics.mean(latencies)
    line = f"{label}: mean={mean:.3f}ms p50={p50:.3f}ms p95={p95:.3f}ms p99={p99:.3f}ms\n"
    with open(_RESULTS_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    _logger.info("BENCH %s", line.strip())


@pytest.fixture(scope="session", autouse=True)
def _clear_results_log():
    if os.path.exists(_RESULTS_LOG):
        os.remove(_RESULTS_LOG)


class TestJsonPerfBaseline:

    def test_read_json_small_file(self, tmp_path):
        data = {"key": "value", "nested": {"a": 1, "b": 2, "c": [1, 2, 3]}}
        p = tmp_path / "small.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        latencies = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            result = fu.read_json(str(p))
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert result == data
        _log_result("read_json_small", latencies)
        assert statistics.median(latencies) < _P50_TOLERANCE_MS

    def test_read_json_large_file(self, tmp_path):
        data = {"items": [{"id": i, "val": f"x{i}" * 100} for i in range(200)]}
        p = tmp_path / "large.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        latencies = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            result = fu.read_json(str(p))
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert result == data
        _log_result("read_json_large", latencies)
        assert statistics.median(latencies) < _P50_TOLERANCE_MS

    def test_write_json_atomic_small(self, tmp_path):
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        p = tmp_path / "out_small.json"
        latencies = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            fu.write_json_atomic(str(p), data)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert p.exists()
        _log_result("write_json_atomic_small", latencies)
        assert statistics.median(latencies) < _P50_TOLERANCE_MS

    def test_write_json_atomic_large(self, tmp_path):
        data = {"items": [{"id": i, "val": f"x{i}" * 100} for i in range(200)]}
        p = tmp_path / "out_large.json"
        latencies = []
        for _ in range(_ITERATIONS):
            start = time.perf_counter()
            fu.write_json_atomic(str(p), data)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert p.exists()
        _log_result("write_json_atomic_large", latencies)
        assert statistics.median(latencies) < _P50_TOLERANCE_MS
