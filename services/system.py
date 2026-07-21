"""System — Détection de l'environnement, venv, chemins des binaires.

Fournit les constantes de chemins et les utilitaires pour :
- Trouver l'interpréteur Python optimal (portable > venv > système).
- Créer et valider un environnement virtuel.
- Installer les dépendances.
- Localiser les binaires externes (ex: Ollama).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from typing import Any, Callable

from config.paths import (
    BIN_DIR,
    OLLAMA_EXE,
    PORTABLE_DIR,
    PORTABLE_LINUX,
    PORTABLE_MAC,
    PORTABLE_PYTHON_EXE,
    REQUIREMENTS_FILE,
    ROOT,
    SYSTEM,
)

BASE_DIR: str = ROOT
PYTHON: str = sys.executable
VENV_DIR: str = os.path.join(BASE_DIR, "venv")


def _venv_python() -> str:
    """Retourne le chemin de l'interpréteur du venv pour la plateforme courante."""
    if SYSTEM == "windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _portable_candidates() -> list[str]:
    """Retourne les chemins potentiels des interpréteurs Python portables."""
    if SYSTEM == "windows":
        return [
            PORTABLE_PYTHON_EXE,
            os.path.join(PORTABLE_DIR, "python.exe"),
        ]
    if SYSTEM == "darwin":
        return [
            PORTABLE_PYTHON_EXE,
            os.path.join(PORTABLE_MAC, "python3"),
        ]
    return [
        PORTABLE_PYTHON_EXE,
        os.path.join(PORTABLE_LINUX, "bin", "python3"),
    ]


def find_python() -> str:
    """Trouve l'interpréteur Python optimal (portable > venv > système).

    Returns:
        Le chemin absolu vers l'interpréteur Python à utiliser.
    """
    candidates = [* _portable_candidates(), _venv_python()]
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
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode != 0
    except OSError:
        return True


def _install_deps(python_path: str, requirements: str, log: Callable[..., Any]) -> bool:
    """Installe les dépendances dans l'interpréteur donné.

    Args:
        python_path: Chemin vers l'interpréteur Python.
        requirements: Chemin vers le fichier requirements.txt.
        log: Fonction de callback pour le logging (signature: step, message, success).

    Returns:
        ``True`` si l'installation a réussi, ``False`` sinon.
    """
    # Mise à jour silencieuse de pip
    with contextlib.suppress(Exception):
        subprocess.run(
            [python_path, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            capture_output=True, timeout=30,
        )
    
    r = subprocess.run(
        [python_path, "-m", "pip", "install", "--quiet", "-r", requirements],
        capture_output=True, text=True, timeout=120,
    )
    
    if r.returncode != 0:
        log("Setup", f"Échec pip install : {r.stderr.strip()}", False)
        return False
    
    log("Setup", "OK", True)
    return True


def ensure_venv(log: Callable[..., Any]) -> str:
    """Prépare l'interpréteur Python (venv ou direct) avec les dépendances.

    Args:
        log: Fonction de callback pour le logging.

    Returns:
        Le chemin vers l'interpréteur Python configuré et prêt à l'emploi.
    """
    selected_py = find_python()
    is_portable = selected_py in _portable_candidates()
    is_embeddable = _is_embeddable(selected_py)

    if is_portable or is_embeddable:
        target_py = selected_py
        log("Setup", "Python portable détecté — utilisation directe", True)
    else:
        target_py = _venv_python()
        if not os.path.exists(target_py):
            log("Setup", "Création de l'environnement virtuel...", None)
            try:
                r = subprocess.run(
                    [selected_py, "-m", "venv", VENV_DIR],
                    capture_output=True, text=True, timeout=30,
                )
            except OSError as exc:
                log("Setup", f"Échec venv : Python incompatible ({exc.strerror})", False)
                log("Setup", "Solution : installez Python 3.12+ depuis python.org", False)
                return selected_py
            
            if r.returncode != 0:
                err = r.stderr.strip()
                log("Setup", f"Échec venv : {err}", False)
                if "ensurepip" in err and sys.platform != "win32":
                    log("Setup", "Solution : sudo apt install python3-venv", False)
                return selected_py
            
            log("Setup", "OK", True)

    # Vérification des dépendances critiques
    import_check = subprocess.run(
        [target_py, "-c", "import fastapi, uvicorn, numpy, httpx, yaml"],
        capture_output=True, text=True, timeout=15,
    )
    
    if import_check.returncode != 0:
        log("Setup", "Installation des dépendances...", None)
        _install_deps(target_py, REQUIREMENTS_FILE, log)

    return target_py


def get_ollama_path() -> str | None:
    """Retourne le chemin du binaire Ollama (portable puis PATH système).

    Returns:
        Le chemin absolu vers le binaire Ollama, ou ``None`` s'il est introuvable.
    """
    name = "ollama.exe" if SYSTEM == "windows" else " each"
    # Correction : "ollama" au lieu de "each" (typo mentale, corrigé ci-dessous)
    name = "ollama.exe" if SYSTEM == "windows" else "ollama"
    
    candidates = [
        OLLAMA_EXE,
        os.path.join(BIN_DIR, name),
    ]
    
    if SYSTEM == "linux":
        candidates.append(os.path.join(BIN_DIR, "ollama-linux-amd64"))
    elif SYSTEM == "darwin":
        candidates.append(os.path.join(BIN_DIR, "ollama-darwin"))
        
    for path in candidates:
        if os.path.exists(path):
            return path
            
    return shutil.which(name)


__all__ = [
    "BASE_DIR",
    "PYTHON",
    "VENV_DIR",
    "find_python",
    "ensure_venv",
    "get_ollama_path",
]
