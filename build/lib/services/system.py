"""System — Détection de l'environnement, venv, chemins des binaires.

Fournit les constantes de chemins (BASE_DIR, BIN_DIR, VENV_DIR)
et les utilitaires : find_python, ensure_venv, get_ollama_path.
"""
import contextlib
import os
import shutil
import subprocess
import sys

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

BASE_DIR = ROOT
PYTHON = sys.executable
VENV_DIR = os.path.join(BASE_DIR, "venv")


def _venv_python() -> str:
    """Chemin de l'interpréteur du venv racine pour la plateforme courante."""
    if SYSTEM == "windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _portable_candidates() -> list[str]:
    """Interpréteurs Python portables supportés, avec compat anciens layouts."""
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


def find_python():
    """Trouve l'interpréteur Python (portable OS > venv > système)."""
    candidates = [*_portable_candidates(), _venv_python()]
    for path in candidates:
        if os.path.exists(path):
            return path
    return PYTHON


def _is_embeddable(python_path: str) -> bool:
    """True si python_path pointe vers un embeddable Python (sans venv)."""
    try:
        r = subprocess.run([python_path, "-c", "import venv, ensurepip"], capture_output=True, text=True, timeout=5)
        return r.returncode != 0
    except OSError:
        return True


def _install_deps(python_path: str, requirements: str, log) -> bool:
    """Installe les dépendances dans l'interpréteur donné. Retourne True si OK."""
    with contextlib.suppress(Exception):
        subprocess.run([python_path, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], capture_output=True, timeout=30)
    r = subprocess.run(
        [python_path, "-m", "pip", "install", "--quiet", "-r", requirements],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        log("Setup", f"Echec pip install : {r.stderr.strip()}", False)
        return False
    log("Setup", "OK")
    return True


def ensure_venv(log) -> str:
    """Prépare l'interpréteur Python (venv ou direct) avec les dépendances."""
    selected_py = find_python()
    is_portable = selected_py in _portable_candidates()
    is_embeddable = _is_embeddable(selected_py)

    if is_portable or is_embeddable:
        target_py = selected_py
        log("Setup", "Python portable detecte — utilisation directe")
    else:
        target_py = _venv_python()
        if not os.path.exists(target_py):
            log("Setup", "Creation de l'environnement virtuel...")
            try:
                r = subprocess.run([selected_py, "-m", "venv", VENV_DIR], capture_output=True, text=True, timeout=30)
            except OSError as exc:
                log("Setup", f"Echec venv : Python incompatible ({exc.strerror})", False)
                log("Setup", "Solution : installez Python 3.12+ depuis python.org", False)
                return selected_py
            if r.returncode != 0:
                err = r.stderr.strip()
                log("Setup", f"Echec venv : {err}", False)
                if "ensurepip" in err and sys.platform != "win32":
                    log("Setup", "Solution : sudo apt install python3-venv", False)
                return selected_py
            log("Setup", "OK")

    import_check = subprocess.run(
        [target_py, "-c", "import fastapi, uvicorn, numpy, httpx, yaml"], capture_output=True, text=True, timeout=15
    )
    if import_check.returncode != 0:
        log("Setup", "Installation des dependances...")
        _install_deps(target_py, REQUIREMENTS_FILE, log)

    return target_py


def get_ollama_path():
    """Retourne le chemin du binaire Ollama (portable puis PATH)."""
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
