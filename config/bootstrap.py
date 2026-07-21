"""Bootstrap — Amorçage de sys.path (zéro dépendance projet).

Garantit que la racine du projet est dans ``sys.path`` afin que les
imports absolus (``from config.x import ...``) fonctionnent depuis
n'importe quel entry point (``jarvis.py``, ``controllers/router.py``,
scripts, tests).

Ce module est volontairement **autonome** : il ne dépend d'aucun autre
module du projet (pas même ``config.paths``). C'est une contrainte
d'amorçage — comme un bootloader, il doit pouvoir tourner avant que le
reste du système ne soit importable. Le calcul de la racine est donc
local et trivial.

Usage ::

    from config.bootstrap import ensure_project_root
    ensure_project_root()
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_root() -> Path:
    """Résout la racine du projet de façon défensive.

    ``__file__`` peut être absent (exécution interactive, ``-c``,
    binaire gelé type PyInstaller) : on retombe alors sur le cwd.
    ``resolve()`` normalise les symlinks et les séparateurs.
    """
    try:
        return Path(__file__).resolve().parent.parent
    except NameError:
        return Path.cwd().resolve()


def _is_present(path: str) -> bool:
    """Vérifie la présence dans sys.path de façon canonique.

    La comparaison normalise casse et séparateurs (critique sous Windows,
    cible prioritaire sur clef USB) pour éviter les doublons fonctionnels
    lorsque la racine y figure déjà sous une forme non résolue (``.``,
    chemin relatif, symlink).
    """
    needle = os.path.normcase(os.path.normpath(path))
    return any(
        os.path.normcase(os.path.normpath(entry)) == needle
        for entry in sys.path
        if entry
    )


def ensure_project_root() -> str:
    """Insère la racine du projet en tête de ``sys.path`` (idempotent).

    L'insertion en position 0 donne la priorité au code local sur les
    packages installés, comportement requis pour un projet portable.

    Returns:
        Le chemin absolu (str) de la racine du projet.
    """
    root_str = str(_resolve_root())
    if not _is_present(root_str):
        sys.path.insert(0, root_str)
    return root_str


__all__ = ["ensure_project_root"]
