"""Port abstrait pour l'évaluation cyber multi-agents."""

from __future__ import annotations

from typing import Any, Protocol


class CyberEvalPort(Protocol):
    """Contrat du service d'évaluation cyber."""

    def analyze(self, question: str, max_revisions: int = 2) -> dict[str, Any]:
        """Évalue la question via le pipeline judge→advocate→evaluator.

        Retourne toujours un dict (jamais None) :
        - decision: "publish" | "revise" | "reject"
        - score: float (0.0-1.0)
        - reasoning: str
        - revisions: int (nombre de tours effectués)

        En cas d'échec pipeline → decision="reject", score=0.0.
        """
        ...


__all__ = ["CyberEvalPort"]
