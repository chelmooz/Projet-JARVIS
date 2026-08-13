"""System — Détection de l'environnement, venv, chemins des binaires.

Fournit les constantes de chemins et les utilitaires pour :
- Trouver l'interpréteur Python optimal (portable > venv > système).
- Créer et valider un environnement virtuel.
- Installer les dépendances.
- Localiser les binaires externes (ex: Ollama).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from services.embeddable_python import enable_site_packages, is_site_enabled

_logger = logging.getLogger(__name__)

from config.paths import (  # noqa: E402  # avoid circular import
    BIN_DIR,
    BIN_LINUX,
    BIN_MAC,
    OLLAMA_EXE,
    PORTABLE_DIR,
    PORTABLE_LINUX,
    PORTABLE_MAC,
    PORTABLE_PYTHON_EXE,
    ROOT,
    SYSTEM,
)

# CORRECTION : Cast explicite de ROOT (Path) en str pour éviter les erreurs de concaténation
BASE_DIR: str = str(ROOT)
PYTHON: str = sys.executable
VENV_DIR: str = os.path.join(BASE_DIR, "venv")


def _venv_python() -> str:
    """Retourne le chemin de l'interpréteur du venv pour la plateforme courante."""
    if SYSTEM == "windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _portable_candidates() -> list[Path]:
    """Retourne les chemins potentiels des interpréteurs Python portables."""
    if SYSTEM == "windows":
        return [
            PORTABLE_PYTHON_EXE,
            PORTABLE_DIR / "python.exe",
        ]
    if SYSTEM == "darwin":
        return [
            PORTABLE_PYTHON_EXE,
            PORTABLE_MAC / "python3",
        ]
    return [
        PORTABLE_PYTHON_EXE,
        PORTABLE_LINUX / "bin" / "python3",
    ]


def find_python() -> str:
    """Trouve l'interpréteur Python optimal (portable > venv > système).

    Returns:
        Le chemin absolu vers l'interpréteur Python à utiliser.
    """
    candidates: list[str] = [str(p) for p in _portable_candidates()]
    candidates.append(_venv_python())
    for path in candidates:
        if os.path.exists(path):
            return path
    return PYTHON


def _is_embeddable(python_path: str) -> bool:
    """Vérifie si l'interpréteur est une version "embeddable" (sans venv/ensurepip).

    Returns:
        ``True`` si les modules ``venv`` ou ``ensurepip`` sont manquants.
    """
    try:
        r = subprocess.run(
            [python_path, "-c", "import venv, ensurepip"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode != 0
    except OSError:
        return True


def _install_deps(python_path: str, project_root: str, log: Callable[..., Any]) -> bool:
    """Installe les dépendances dans l'interpréteur donné via pip install -e .

    Args:
        python_path: Chemin vers l'interpréteur Python.
        project_root: Chemin racine du projet (contenant pyproject.toml).
        log: Fonction de callback pour le logging (signature: step, message, success).

    Returns:
        ``True`` si l'installation a réussi, ``False`` sinon.
    """
    # Mise à jour silencieuse de pip (best-effort)
    try:
        subprocess.run(
            [python_path, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            capture_output=True,
            timeout=30,
        )
        _logger.info("pip mis à jour avec succès")
    except Exception as e:
        _logger.debug("pip upgrade skipped: %s", e)

    r = subprocess.run(
        [python_path, "-m", "pip", "install", "--quiet", "-e", project_root],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if r.returncode != 0:
        log("Setup", f"Échec pip install : {r.stderr.strip()}", False)
        return False

    log("Setup", "OK", True)
    return True


def ensure_venv(log: Callable[..., Any]) -> tuple[str, bool]:
    """Prépare l'interpréteur Python (venv ou direct) avec les dépendances.

    Args:
        log: Fonction de callback pour le logging.

    Returns:
        Un tuple ``(python_path, restart_required)``. ``restart_required``
        est True quand l'interpréteur cible doit redémarrer pour que ses
        changements prennent effet — soit parce que son fichier ``._pth``
        vient d'être patché (site-packages activé : un embeddable ne relit
        ce fichier qu'au démarrage), soit parce qu'un venv distinct de
        l'interpréteur courant a été sélectionné.
    """
    selected_py = find_python()
    is_portable = any(Path(selected_py) == candidate for candidate in _portable_candidates())
    is_embeddable = _is_embeddable(selected_py)
    restart_required = False

    if is_portable or is_embeddable:
        target_py = selected_py
        if not is_site_enabled(target_py):
            if enable_site_packages(target_py):
                log(
                    "Setup",
                    "site-packages activé (._pth corrigé) — redémarrage requis",
                    True,
                )
                restart_required = True
            else:
                log(
                    "Setup",
                    "Échec activation site-packages (._pth) : les dépendances "
                    "installées resteront invisibles à l'import",
                    False,
                )
        log("Setup", "Python portable détecté — utilisation directe", True)
    else:
        target_py = _venv_python()
        if not os.path.exists(target_py):
            log("Setup", "Création de l'environnement virtuel...", None)
            try:
                r = subprocess.run(
                    [selected_py, "-m", "venv", VENV_DIR],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except OSError as exc:
                log("Setup", f"Échec venv : Python incompatible ({exc.strerror})", False)
                log("Setup", "Solution : installez Python 3.12+ depuis python.org", False)
                return selected_py, False

            if r.returncode != 0:
                err = r.stderr.strip()
                log("Setup", f"Échec venv : {err}", False)
                if "ensurepip" in err and sys.platform != "win32":
                    log("Setup", "Solution : sudo apt install python3-venv", False)
                return selected_py, False

            log("Setup", "OK", True)

    # Vérification des dépendances critiques
    import_check = subprocess.run(
        [target_py, "-c", "import fastapi, uvicorn, numpy, httpx, yaml"],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if import_check.returncode != 0:
        log("Setup", "Installation des dépendances...", None)
        _install_deps(target_py, BASE_DIR, log)

    return target_py, restart_required


def get_ollama_path() -> str | None:
    """Retourne le chemin du binaire Ollama (portable puis PATH système).

    Returns:
        Le chemin absolu vers le binaire Ollama, ou ``None`` s'il est introuvable.
    """
    # CORRECTION : Nettoyage de la typo "each"
    name = "ollama.exe" if SYSTEM == "windows" else "ollama"

    candidates: list[str] = [
        str(OLLAMA_EXE),
        os.path.join(str(BIN_DIR), name),
    ]

    if SYSTEM == "linux":
        candidates.append(os.path.join(str(BIN_DIR), "ollama-linux-amd64"))
    elif SYSTEM == "darwin":
        candidates.append(os.path.join(str(BIN_DIR), "ollama-darwin"))

    for path in candidates:
        if os.path.exists(path):
            return path

    return shutil.which(name)


__all__ = [
    "BASE_DIR",
    "BIN_DIR",
    "PYTHON",
    "VENV_DIR",
    "BIN_LINUX",
    "BIN_MAC",
    "PORTABLE_DIR",
    "PORTABLE_PYTHON_EXE",
    "ROOT",
    "SYSTEM",
    "OLLAMA_EXE",
    "find_python",
    "ensure_venv",
    "get_ollama_path",
]
