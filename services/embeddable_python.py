"""EmbeddablePython — Active site-packages sur un Python embeddable Windows.

Les zips "embeddable" officiels (python.org/.../python-X.Y.Z-embed-amd64.zip)
livrent un fichier ``<version>._pth`` qui désactive le module ``site`` par
défaut : ``Lib\\site-packages`` n'est alors JAMAIS ajouté à ``sys.path``,
même après un ``pip install`` réussi. Résultat : les paquets installés
existent sur disque mais restent invisibles à l'import (source du
``ModuleNotFoundError`` malgré une installation "OK").

Responsabilité unique : lire/patcher ce fichier ``._pth``. Ne sait rien de
venv, de pip, ni du cycle de vie du processus (le redémarrage nécessaire
après patch est orchestré par services.dependency_bootstrap).
"""

from __future__ import annotations

import os

_SITE_LINE = "import site"


def _pth_file(python_dir: str) -> str | None:
    """Retourne le chemin du fichier ``._pth`` du dossier, ou None s'il n'y
    en a pas (interpréteur non-embeddable — rien à patcher)."""
    try:
        entries = os.listdir(python_dir)
    except OSError:
        return None
    for name in entries:
        if name.endswith("._pth"):
            return os.path.join(python_dir, name)
    return None


def is_site_enabled(python_exe: str) -> bool:
    """True si ``site`` est déjà activé (ou si ce n'est pas un embeddable)."""
    pth = _pth_file(os.path.dirname(python_exe))
    if pth is None:
        return True
    try:
        with open(pth, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return True
    return any(line.strip() == _SITE_LINE for line in lines)


def enable_site_packages(python_exe: str) -> bool:
    """Active ``import site`` dans le fichier ``._pth`` si nécessaire.

    Idempotent : ne touche rien si déjà activé ou si l'interpréteur n'est
    pas une distribution embeddable (pas de fichier ``._pth``).

    Returns:
        True si l'état final est "site activé" (déjà activé, ou patché
        avec succès, ou rien à faire) ; False si un fichier ``._pth``
        existe mais n'a pas pu être modifié.
    """
    python_dir = os.path.dirname(python_exe)
    pth = _pth_file(python_dir)
    if pth is None:
        return True

    try:
        with open(pth, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return False

    if any(line.strip() == _SITE_LINE for line in content.splitlines()):
        return True

    modified = content.replace(f"#{_SITE_LINE}", _SITE_LINE)
    if _SITE_LINE not in modified:
        modified = modified.rstrip("\n") + f"\n{_SITE_LINE}\n"

    try:
        with open(pth, "w", encoding="utf-8") as fh:
            fh.write(modified)
    except OSError:
        return False
    return True


__all__ = ["is_site_enabled", "enable_site_packages"]
