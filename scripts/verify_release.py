"""Contrôles non destructifs avant de distribuer une archive JARVIS.

Usage : ``python scripts/verify_release.py`` depuis la racine du projet.
Le script ne contacte aucun service externe et ne modifie aucun fichier.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")

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


def version_sources() -> dict[str, str]:
    """Extrait la version annoncée de chaque source (pyproject, constants, VERSION.json, launchers)."""
    sources: dict[str, str] = {}

    try:
        import tomllib

        with open(PROJECT_ROOT / "pyproject.toml", "rb") as fh:
            sources["pyproject.toml"] = tomllib.load(fh)["project"]["version"]
    except (ImportError, OSError, KeyError, ValueError) as exc:
        sources["pyproject.toml"] = f"<erreur lecture : {exc}>"

    constants_file = PROJECT_ROOT / "config" / "constants.py"
    try:
        match = re.search(r'VERSION:\s*Final\[str\]\s*=\s*"([^"]+)"', constants_file.read_text(encoding="utf-8"))
        sources["config/constants.py"] = match.group(1) if match else "<VERSION introuvable>"
    except OSError as exc:
        sources["config/constants.py"] = f"<erreur lecture : {exc}>"

    version_json = PROJECT_ROOT / "bin" / "VERSION.json"
    try:
        sources["bin/VERSION.json"] = json.loads(version_json.read_text(encoding="utf-8"))["app"]["version"]
    except (OSError, KeyError, ValueError) as exc:
        sources["bin/VERSION.json"] = f"<erreur lecture : {exc}>"

    for launcher in ("launchers/JARVIS.bat", "launchers/JARVIS.sh"):
        try:
            content = (PROJECT_ROOT / launcher).read_text(encoding="utf-8", errors="replace")
            match = re.search(r"(?:v|JARVIS_VERSION=)\s*\"?(\d+\.\d+(?:\.\d+)?)", content)
            sources[launcher] = match.group(1) if match else "<version introuvable>"
        except OSError as exc:
            sources[launcher] = f"<erreur lecture : {exc}>"

    return sources


def check_version_coherence(failures: list[str]) -> None:
    """Vérifie que toutes les sources annoncent la même version."""
    sources = version_sources()
    valid = {name: version for name, version in sources.items() if VERSION_RE.match(version)}
    if not valid:
        failures.append(f"Aucune version lisible : {sources}")
        return
    baseline = next(iter(valid.values()))
    for name, version in valid.items():
        if version != baseline:
            failures.append(f"Version incohérente : {name} = {version} (pyproject.toml = {baseline})")
    for name, version in sources.items():
        if not VERSION_RE.match(version):
            failures.append(f"Version illisible : {name} = {version}")


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

    check_version_coherence(failures)

    if failures:
        print("ÉCHEC — archive non prête à distribuer :")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "OK — contrôles de livraison réussis : fichiers requis présents, secrets locaux absents, versions cohérentes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
