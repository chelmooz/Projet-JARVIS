#!/usr/bin/env python3
"""
JARVIS Portable — Génère le badge de couverture (format shields.io endpoint).

Lit le rapport pytest-cov ``coverage.json`` (--cov-report=json, ligne 1) et
écrit ``coverage-badge.json`` à la racine, consommé par le README via
`shields.io/endpoint`. Exécuté par la CI à chaque push (job quality) et
manuellement en local : ``python scripts/coverage_badge.py``.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT = PROJECT_ROOT / "coverage.json"
OUTPUT = PROJECT_ROOT / "coverage-badge.json"


def color_for(percent: float) -> str:
    """Couleur du badge selon le seuil (rouge < 50, orange < 70, jaune < 90, vert sinon)."""
    if percent < 50:
        return "red"
    if percent < 70:
        return "orange"
    if percent < 90:
        return "yellow"
    return "brightgreen"


def main() -> int:
    """Génère coverage-badge.json depuis le rapport pytest-cov."""
    if not REPORT.is_file():
        print(f"Rapport introuvable : {REPORT}")
        print("Générer d'abord : pytest --cov --cov-report=json")
        return 1

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    percent = float(data["totals"]["percent_covered"])

    badge = {
        "schemaVersion": 1,
        "label": "coverage",
        "message": f"{percent:.1f}%",
        "color": color_for(percent),
    }
    OUTPUT.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")
    print(f"Badge écrit : {OUTPUT} ({badge['message']}, {badge['color']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
