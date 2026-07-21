"""Résolution du chemin d'un binaire à partir de la configuration.

Gère les spécificités de plateforme (Windows vs Linux/macOS) et la
recherche dans le PATH système avant de se rabattre sur le répertoire
binaire local (bin_dir).
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any


def resolve_binary(config: dict[str, Any], tool_name: str, bin_dir: str) -> str | None:
    """Résout le chemin absolu d'un binaire externe.

    Args:
        config: Dictionnaire de configuration global (doit contenir la clé "tools").
        tool_name: Nom de l'outil tel qu'attendu dans la configuration.
        bin_dir: Répertoire local contenant les binaires portables.

    Returns:
        Le chemin absolu vers le binaire s'il est trouvé, sinon ``None``.
    """
    cfg = config.get("tools", {}).get(tool_name)
    if not cfg:
        return None

    # Détermination du nom du binaire selon la plateforme
    if sys.platform == "win32":
        binary = cfg.get("binary")
        path = os.path.join(bin_dir, binary) if binary else None
    else:
        # Sur Unix, on cherche d'abord dans le PATH système, puis dans bin_dir
        binary = cfg.get("linux_binary") or cfg.get("binary")
        if not binary:
            return None
        path = shutil.which(binary)
        if not path:
            path = os.path.join(bin_dir, binary)

    # Vérification finale de l'existence (isfile pour exclure les répertoires)
    if path and os.path.isfile(path):
        return os.path.abspath(path)

    return None


__all__ = ["resolve_binary"]
