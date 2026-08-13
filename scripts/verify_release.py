"""Contrôles non destructifs avant de distribuer une archive JARVIS.

Usage : ``python scripts/verify_release.py`` depuis la racine du projet.
Le script ne contacte aucun service externe et ne modifie aucun fichier.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "pyproject.toml",
    "jarvis.py",
    "static/index.html",
    "static/assets/css/style.css",
    "static/assets/js/app.js",
    "services/ollama_installer.py",
    "tests/test_ollama_installer_security.py",
)

FORBIDDEN_FILES = (
    ".env",
    ".env.local",
    "config/model_preferences.json",
    "config/file_authorized_paths.json",
)


def main() -> int:
    """Vérifie les éléments attendus d'une distribution source propre."""
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).is_file():
            failures.append(f"Fichier requis absent : {relative_path}")

    for relative_path in FORBIDDEN_FILES:
        if (PROJECT_ROOT / relative_path).exists():
            failures.append(f"Fichier de configuration locale à exclure : {relative_path}")

    for cache_dir in ("__pycache__", ".pytest_cache", ".pytest-temp", ".ruff_cache"):
        if any(PROJECT_ROOT.rglob(cache_dir)):
            failures.append(f"Cache d'exécution à exclure : {cache_dir}")

    if failures:
        print("ÉCHEC — archive non prête à distribuer :")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("OK — contrôles de livraison réussis : fichiers requis présents, secrets locaux absents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
