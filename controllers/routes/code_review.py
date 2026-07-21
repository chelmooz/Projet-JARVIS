"""Route API — Code Review : sécurité, performance, maintenabilité."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from controllers.responses import ok
from services.analysis import Analyzer as CodeReviewAnalyzer

router = APIRouter()


def get_analyzer() -> CodeReviewAnalyzer:
    """Dépendance : fournit une instance de l'analyseur Code Review."""
    return CodeReviewAnalyzer()


@router.get("/api/code-review/file")
def review_file(
    path: str = Query(..., description="Chemin absolu du fichier Python"),
    analyzer: CodeReviewAnalyzer = Depends(get_analyzer),
):
    """Revue complète sécurité + performance + maintenabilité d'un fichier Python.

    Laisse sync : analyse disque/CPU bloquant (lecture + parse du fichier).
    """
    report = analyzer.review_file(path)
    return ok(report)


@router.get("/api/code-review/project")
def review_project(
    path: str = Query(".", description="Chemin du répertoire racine"),
    analyzer: CodeReviewAnalyzer = Depends(get_analyzer),
):
    """Revue de tous les fichiers Python d'un projet.

    Laisse sync : analyse complète (lecture/parse de tous les fichiers, CPU/IO).
    """
    results = analyzer.analyze_project(path)
    if not results:
        return ok({"files": 0, "total_findings": 0, "average_score": 100.0, "reports": []})

    # Robustesse : getattr pour gérer les objets dataclass ou dicts selon l'implémentation
    total_findings = sum(getattr(r, "total", 0) for r in results)
    avg_score = round(sum(getattr(r, "score", 0) for r in results) / len(results), 1)
    
    return ok({
        "files": len(results),
        "total_findings": total_findings,
        "average_score": avg_score,
        "reports": [dict(r) for r in results],
    })


__all__ = ["router"]
