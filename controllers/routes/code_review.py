"""Route API — Code Review : sécurité, performance, maintenabilité."""
from fastapi import APIRouter, Query

from services.analysis import Analyzer as CodeReviewAnalyzer

router = APIRouter()
_analyzer = CodeReviewAnalyzer()


@router.get("/api/code-review/file")
def review_file(path: str = Query(..., description="Chemin absolu du fichier Python")):
    # Laisse sync : analyse disque/CPU bloquant (lecture + parse du fichier).
    """Revue complète sécurité + performance + maintenabilité d'un fichier Python."""
    report = _analyzer.review_file(path)
    return report


@router.get("/api/code-review/project")
def review_project(path: str = Query(".", description="Chemin du repertoire racine")):
    # Laisse sync : analyse complète (lecture/parse de tous les fichiers, CPU/IO).
    """Revue de tous les fichiers Python d'un projet."""
    results = _analyzer.analyze_project(path)
    total_findings = sum(r.total for r in results)
    avg_score = round(sum(r["score"] for r in results) / len(results), 1) if results else 100
    return {
        "files": len(results),
        "total_findings": total_findings,
        "average_score": avg_score,
        "reports": [dict(r) for r in results],
    }
