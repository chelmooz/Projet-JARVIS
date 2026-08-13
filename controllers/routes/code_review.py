"""Route API — Code Review : sécurité, performance, maintenabilité."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from controllers.responses import fail, ok
from services.analysis import Analyzer as CodeReviewAnalyzer
from services.file_system import FileSystemService

router = APIRouter()
_fs = FileSystemService()


def get_analyzer() -> CodeReviewAnalyzer:
    """Dépendance : fournit une instance de l'analyseur Code Review."""
    return CodeReviewAnalyzer()


@router.get("/api/code-review/file")
def review_file(
    path: str = Query(..., description="Chemin absolu du fichier Python"),
    analyzer: CodeReviewAnalyzer = Depends(get_analyzer),
) -> Any:
    """Revue complète sécurité + performance + maintenabilité d'un fichier Python."""
    if not _fs.authorize_path(path):
        return fail("Chemin non autorisé (hors sandbox)", status_code=403)
    report: dict[str, Any] = analyzer.analyze_file(path)
    return ok(report)


@router.get("/api/code-review/project")
def review_project(
    path: str = Query(".", description="Chemin du répertoire racine"),
    analyzer: CodeReviewAnalyzer = Depends(get_analyzer),
) -> Any:
    """Revue de tous les fichiers Python d'un projet."""
    if not _fs.authorize_path(path):
        return fail("Chemin non autorisé (hors sandbox)", status_code=403)
    results = analyzer.analyze_project(path)
    if not results:
        return ok({"files": 0, "total_findings": 0, "average_score": 100.0, "reports": []})

    total_findings = sum(r.total for r in results)
    avg_score = round(sum(r["score"] for r in results) / len(results), 1)

    return ok(
        {
            "files": len(results),
            "total_findings": total_findings,
            "average_score": avg_score,
            "reports": [dict(r) for r in results],
        }
    )


__all__ = ["router"]
