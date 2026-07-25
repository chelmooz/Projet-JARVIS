#!/usr/bin/env python3
"""Benchmark Runner — exécute tests/bench I/O et rapporte P50/P95/P99.

Usage:
    python scripts/bench_runner.py          # run + rapport
    python scripts/bench_runner.py --json   # sortie JSON uniquement

Le test ``tests/test_io_perf.py::TestJsonPerfBaseline`` est exécuté et les
métriques sont extraites du fichier ``test_io_perf_results.log``.
"""

import argparse
import json
import os
import re
import subprocess
import sys

_RESULTS_LOG = os.path.join(os.path.dirname(__file__), "..", "test_io_perf_results.log")

LINE_RE = re.compile(
    r"^(?P<label>\w+): mean=(?P<mean>[\d.]+)ms p50=(?P<p50>[\d.]+)ms "
    r"p95=(?P<p95>[\d.]+)ms p99=(?P<p99>[\d.]+)ms$"
)


def run_bench() -> dict[str, dict[str, float]]:
    """Lance pytest sur test_io_perf et parse le fichier de résultats."""
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/test_io_perf.py", "-v"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)

    if not os.path.exists(_RESULTS_LOG):
        print("[FAIL] Aucun fichier de résultats trouvé")
        sys.exit(1)

    metrics = {}
    with open(_RESULTS_LOG, encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.match(line.strip())
            if m:
                metrics[m.group("label")] = {
                    "mean_ms": float(m.group("mean")),
                    "p50_ms": float(m.group("p50")),
                    "p95_ms": float(m.group("p95")),
                    "p99_ms": float(m.group("p99")),
                }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Benchmark Runner I/O")
    parser.add_argument("--json", action="store_true", help="Sortie JSON uniquement")
    args = parser.parse_args()

    metrics = run_bench()

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    print("\n" + "=" * 50)
    print("RAPPORT DE PERFORMANCE I/O (orjson)")
    print("=" * 50)
    for label, m in sorted(metrics.items()):
        print(f"\n[{label}]")
        print(f"  Mean : {m['mean_ms']:.3f} ms")
        print(f"  P50  : {m['p50_ms']:.3f} ms")
        print(f"  P95  : {m['p95_ms']:.3f} ms")
        print(f"  P99  : {m['p99_ms']:.3f} ms")

    print("\n" + "=" * 50)
    print(f"{len(metrics)} benchmarks exécutés")


if __name__ == "__main__":
    main()
