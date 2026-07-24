"""Route API — Kill Coding : analyse SOLID/TDD/Clean Code/KISS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from controllers.responses import fail, ok
from services.analysis import Analyzer as KillCodingAnalyzer
from services.file_system import FileSystemService

router = APIRouter()
_fs = FileSystemService()


def get_analyzer() -> KillCodingAnalyzer:
    """Dépendance : fournit une instance de l'analyseur Kill Coding."""
    return KillCodingAnalyzer()


@router.get("/api/kill-coding/analyze")
def analyze_file(
    path: str = Query(..., description="Chemin absolu du fichier Python"),
    analyzer: KillCodingAnalyzer = Depends(get_analyzer),
):
    """Analyse un fichier Python selon les règles SOLID/TDD/Clean Code/KISS."""
    if not _fs.authorize_path(path):
        return fail("Chemin non autorisé (hors sandbox)", status_code=403)
    report = analyzer.analyze_file(path)
    return ok(report)


@router.get("/api/kill-coding/project")
def analyze_project(
    path: str = Query(".", description="Chemin du répertoire racine"),
    analyzer: KillCodingAnalyzer = Depends(get_analyzer),
):
    """Audit complet d'un projet Python."""
    if not _fs.authorize_path(path):
        return fail("Chemin non autorisé (hors sandbox)", status_code=403)
    report = analyzer.generate_global_report(root=path)
    return ok(report)


@router.get("/api/kill-coding/check-test")
def check_test(
    path: str = Query(..., description="Chemin absolu du fichier source"),
    analyzer: KillCodingAnalyzer = Depends(get_analyzer),
):
    """Vérifie si un fichier source a des tests associés (TDD)."""
    if not _fs.authorize_path(path):
        return fail("Chemin non autorisé (hors sandbox)", status_code=403)
    result = analyzer.check_test_exists(path)
    if result.get("test_found"):
        return ok({
            "message": "Test trouvé",
            "test_paths": result.get("test_paths", []),
        })
    return fail("Aucun test associé", status_code=404)


__all__ = ["router"]
