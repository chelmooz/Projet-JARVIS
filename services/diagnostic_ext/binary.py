"""Résolution du chemin d'un binaire à partir de la configuration.

Gère les spécificités de plateforme (Windows vs Linux/macOS) et la
recherche dans le PATH système avant de se rabattre sur le répertoire
binaire local (bin_dir), organisé en sous-dossier par OS.
"""

from __future__ import annotations

import os
import platform as _platform
import shutil
import sys
from typing import Any

# Sous-dossier par plateforme dans bin_dir (ex: bin/diagnostic/win).
# Permet de faire coexister un witr Linux (ELF) et un witr macOS (Mach-O)
# qui portent le même nom sans collision.
_PLATFORM_SUBDIR = {"win32": "win", "linux": "linux", "darwin": "darwin"}


def resolve_binary(config: dict[str, Any], tool_name: str, bin_dir: str) -> str | None:
    """Résout le chemin absolu d'un binaire externe.

    Le répertoire binaire local est organisé par OS : ``<bin_dir>/win``,
    ``<bin_dir>/linux``, ``<bin_dir>/darwin`` (cohérent avec l'existant
    ``bin/linux``, ``bin/mac``, ``bin/win`` pour Ollama).

    Args:
        config: Dictionnaire de configuration global (doit contenir la clé "tools").
        tool_name: Nom de l'outil tel qu'attendu dans la configuration.
        bin_dir: Répertoire local racine des binaires portables.

    Returns:
        Le chemin absolu vers le binaire s'il est trouvé, sinon ``None``.
    """
    cfg = config.get("tools", {}).get(tool_name)
    if not cfg:
        return None

    subdir = _PLATFORM_SUBDIR.get(sys.platform, sys.platform)
    platform_bin_dir = os.path.join(bin_dir, subdir)

    if sys.platform == "win32":
        # Windows : binaire local dans le sous-dossier de l'OS
        binary = cfg.get("binary")
        path = os.path.join(platform_bin_dir, binary) if binary else None
    else:
        # Unix : PATH système en priorité, repli sur le sous-dossier local
        if sys.platform == "darwin":
            binary = cfg.get("darwin_binary") or cfg.get("linux_binary") or cfg.get("binary")
        else:
            binary = cfg.get("linux_binary") or cfg.get("binary")
        if not binary:
            return None
        path = shutil.which(binary)
        if not path:
            path = os.path.join(platform_bin_dir, binary)

    # Vérification finale de l'existence (isfile pour exclure les répertoires)
    if path and os.path.isfile(path):
        return os.path.abspath(path)

    return None


def resolve_expected_sha256(config: dict[str, Any], tool_name: str, platform: str) -> str:
    """Résout le hash SHA256 attendu pour un outil sur la plateforme donnée.

    Même schéma que ``resolve_binary`` : la plateforme win32 utilise la clé
    ``sha256``, les autres plateformes la clé ``{platform}_sha256`` (ex:
    ``linux_sha256``), avec repli documenté sur ``sha256`` si la clé
    spécifique est absente.

    Pour Darwin, distingue arm64 vs amd64 via ``platform.machine()`` :
    - ``darwin_sha256`` : arm64 (Apple Silicon)
    - ``darwin_amd64_sha256`` : x86_64 (Intel)

    Args:
        config: Dictionnaire de configuration global (clé "tools").
        tool_name: Nom de l'outil tel qu'attendu dans la configuration.
        platform: ``sys.platform`` (win32, linux, darwin…).

    Returns:
        Le hash attendu (vide = vérification ignorée).
    """
    cfg = config.get("tools", {}).get(tool_name)
    if not cfg:
        return ""
    if platform == "win32":
        return cfg.get("sha256", "")
    if platform == "darwin":
        machine = _platform.machine().lower()
        if machine in ("amd64", "x86_64"):
            return cfg.get("darwin_amd64_sha256") or cfg.get("darwin_sha256") or cfg.get("sha256", "")
        return cfg.get("darwin_sha256") or cfg.get("darwin_amd64_sha256") or cfg.get("sha256", "")
    return cfg.get(f"{platform}_sha256", cfg.get("sha256", ""))


__all__ = ["resolve_binary", "resolve_expected_sha256"]
