"""Bootstrap — Garantit que la racine du projet est dans sys.path.

Point central unique pour l'insert sys.path, évite la duplication dans
jarvis.py, controllers/router.py, et autres entry points.
Usage ::

    from config.bootstrap import ensure_project_root
    ensure_project_root()
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_project_root() -> str:
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    return _PROJECT_ROOT
