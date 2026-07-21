"""Route API — Kill Coding : analyse SOLID/TDD/Clean Code/KISS."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.analysis import Analyzer as KillCodingAnalyzer

router = APIRouter()
_analyzer = KillCodingAnalyzer()


@router.get("/api/kill-coding/analyze")
def analyze_file(path: str = Query(..., description="Chemin absolu du fichier Python")):
    # Laisse sync : analyse disque/CPU bloquant (lecture + parse du fichier).
    """Analyse un fichier Python selon les regles SOLID/TDD/Clean Code/KISS."""
    report = _analyzer.analyze_file(path)
    return report


@router.get("/api/kill-coding/project")
def analyze_project(path: str = Query(".", description="Chemin du repertoire racine")):
    # Laisse sync : audit complet (lecture/parse de tous les fichiers, CPU/IO).
    """Audit complet d'un projet Python."""
    report = _analyzer.generate_global_report(root=path)
    return report


@router.get("/api/kill-coding/check-test")
def check_test(path: str = Query(..., description="Chemin absolu du fichier source")):
    # Laisse sync : parcours disque bloquant (recherche de fichiers de test).
    """Verifie si un fichier source a des tests associes (TDD)."""
    result = _analyzer.check_test_exists(path)
    if result["test_found"]:
        return {"status": "ok", "message": "Test trouve", "test_paths": result["test_paths"]}
    return JSONResponse({"status": "missing", "message": "Aucun test associe"}, status_code=404)
