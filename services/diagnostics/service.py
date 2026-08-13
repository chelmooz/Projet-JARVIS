"""DiagnosticService — Orchestration des 8 checks + recommandations + verdict + affichage.
API publique identique à l'ancienne classe monolithique."""

from typing import Any

from services.diagnostics.checks import (
    check_binaries,
    check_cpu,
    check_disk,
    check_gpu,
    check_network,
    check_os,
    check_python,
    check_ram,
)
from services.diagnostics.report import print_report as _print_report
from services.diagnostics.rules import compute_verdict, generate_recommendations


class DiagnosticService:
    def __init__(self) -> None:
        self._results: dict[str, Any] = {}

    def check_os(self) -> dict[str, Any]:
        return check_os()

    def check_cpu(self) -> dict[str, Any]:
        return check_cpu()

    def check_ram(self) -> dict[str, Any]:
        return check_ram()

    def check_gpu(self) -> dict[str, Any]:
        return check_gpu()

    def check_python(self) -> dict[str, Any]:
        return check_python()

    def check_binaries(self) -> list[dict[str, Any]]:
        return check_binaries()

    def check_network(self) -> dict[str, Any]:
        return check_network()

    def check_disk(self) -> dict[str, Any]:
        return check_disk()

    def run_full(self) -> dict[str, Any]:
        self._results = {
            "host": self.check_os(),
            "cpu": self.check_cpu(),
            "ram": self.check_ram(),
            "gpu": self.check_gpu(),
            "python": self.check_python(),
            "binaries": self.check_binaries(),
            "network": self.check_network(),
            "disk": self.check_disk(),
        }
        self._results["recommendations"] = generate_recommendations(self._results)
        self._results["verdict"] = compute_verdict(self._results["recommendations"])
        return self._results

    def print_report(self) -> None:
        recs = self._results.get("recommendations", [])
        verdict = self._results.get("verdict", "?")
        _print_report(recs, verdict)
