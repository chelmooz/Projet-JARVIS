#!/usr/bin/env python3
"""
JARVIS Portable Edition — Installateur multi-OS
Detecte automatiquement Windows / Linux / macOS.
Installe les dependances Python, Ollama et OpenWebUI.
"""

import os
import platform
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM = platform.system().lower()
ARCH = platform.machine()


def color(text, code):
    """Color."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(text):   return color(text, "92")
def yellow(text):  return color(text, "93")
def cyan(text):    return color(text, "96")
def red(text):     return color(text, "91")
def gray(text):    return color(text, "90")


def header():
    """Header."""
    subprocess.run("cls" if SYSTEM == "windows" else "clear", shell=True)
    print(cyan("====================================================="))
    print(cyan("  JARVIS Portable Edition v5.6"))
    print(cyan("  Installateur multi-OS"))
    print(cyan("====================================================="))
    print(f"  Systeme : {SYSTEM} / {ARCH}")
    print()


def install_python_deps():
    """Installe les packages Python."""
    print(yellow("\n[2/3] Dependances Python..."))

    # Utiliser pyproject.toml comme source unique de vérité
    project_file = os.path.join(BASE_DIR, "pyproject.toml")
    if not os.path.exists(project_file):
        print(red("  pyproject.toml introuvable"))
        return False

    # Utiliser le venv du projet s'il existe, sinon l'executable courant
    pip_exe = sys.executable
    venv_dir = os.path.join(BASE_DIR, "venv")
    if os.path.isdir(venv_dir):
        if SYSTEM == "windows":
            candidate = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            candidate = os.path.join(venv_dir, "bin", "python")
        if os.path.exists(candidate):
            pip_exe = candidate

    # Installer depuis pyproject.toml (dependances dans [project.dependencies])
    cmd = [pip_exe, "-m", "pip", "install", "."]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  {green('[OK] Packages Python installes depuis pyproject.toml')}")
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode()
        print(red(f"  Erreur pip: {err[:300]}"))
        if "externally-managed-environment" in err:
            print(red("  PEP 668: Environnement systeme protege."))
            print(gray("  Solution : utilisez le Python portable de JARVIS ou creez un venv :"))
            print(cyan("    python3 -m venv venv"))
            print(cyan("    source venv/bin/activate  (Linux/macOS)"))
            print(cyan("    .\\venv\\Scripts\\activate  (Windows)"))
        else:
            print(gray("  Verifiez votre connexion ou les logs ci-dessus."))
        return False


def setup_ollama():
    """Installe le binaire Ollama **portable** SUR LA CLÉ (jamais sur l'ordi client).

    Les machines à auditer ne sont PAS la machine de déploiement : une installation
    système (Ollama installé via irm/apt/brew sur le poste client) est inutile et
    interdite. Le binaire portable est posé dans bin/ (sur la clé) ; s'il manque,
    JARVIS.bat le téléchargera au premier lancement (ensure_ollama_binary).
    """
    print(yellow("\n[2/3] Ollama (moteur d'inference — portable SUR LA CLE)..."))

    existing = _portable_ollama_path()
    if existing:
        print(f"  {green('[OK]')} Binaire portable deja present sur la cle : {existing}")
        return True

    print(gray("  Aucun binaire portable trouve dans bin/ — il sera telecharge"))
    print(gray("  directement sur la cle USB (jamais sur l'ordi client)."))

    try:
        if sys.stdin.isatty():
            resp = input(gray("  Installer Ollama portable sur la cle ? [y/N] ")).strip().lower()
            if resp != "y":
                print(gray("  Ignore. JARVIS.bat le telechargera automatiquement au 1er lancement."))
                return False
    except (EOFError, KeyboardInterrupt):
        return False

    sys.path.insert(0, BASE_DIR)
    from services.ollama_installer import (
        _install_linux_tar,
        _install_mac_brew,
        _install_mac_script,
        _install_windows_zip,
    )

    def log(step, message, success):
        mark = green("[OK]") if success else (red("[FAIL]") if success is False else gray("..."))
        print(f"      {mark} {step} : {message}")

    try:
        if SYSTEM == "windows":
            result = _install_windows_zip(log)
        elif SYSTEM == "linux":
            result = _install_linux_tar(log)
        else:
            # macOS : pas de binaire portable packagé dans le dépôt — on tente
            # brew/script, mais JARVIS reste utilisable sinon.
            result = _install_mac_brew(log) or _install_mac_script(log)
    except Exception as e:
        print(red(f"  Erreur: {e}"))
        print(gray("  JARVIS.bat retentera automatiquement au 1er lancement."))
        return False

    if result:
        print(f"  {green('[OK]')} Binaire portable installe : {result}")
        return True

    print(red("  Echec du telechargement portable."))
    print(gray("  JARVIS.bat retentera automatiquement au 1er lancement."))
    return False


def install_openwebui():
    """Installe OpenWebUI via pip."""
    print(yellow("\n[3/3] OpenWebUI (interface utilisateur)..."))

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "open-webui"],
            capture_output=True, timeout=300
        )
        if result.returncode == 0:
            print(f"  {green('[OK]')} OpenWebUI installe")
            return True
        else:
            err = result.stderr.decode()[:200]
            print(red(f"  Erreur: {err}"))
            print(gray("  Installez-le manuellement : pip install open-webui"))
            return False
    except subprocess.TimeoutExpired:
        print(red("  Timeout (5 min) — installez manuellement : pip install open-webui"))
        return False


def _portable_ollama_path():
    """Retourne le chemin du binaire Ollama portable s'il existe sur la clé, sinon None."""
    name = "ollama.exe" if SYSTEM == "windows" else "ollama"
    subdirs = {"windows": [""], "linux": ["linux"], "darwin": ["mac"]}
    for sub in subdirs.get(SYSTEM, [""]):
        candidate = os.path.join(BASE_DIR, "bin", sub, name) if sub else os.path.join(BASE_DIR, "bin", name)
        if os.path.exists(candidate):
            return candidate
    return None


def print_final(ollama_portable_path=None):
    """Print final.

    ollama_portable_path : chemin du binaire Ollama portable détecté sur la clé
    (bin\\ollama.exe / bin/linux/ollama / bin/mac/ollama), ou None si absent —
    auto-détecté si non fourni. CORRECTION : n'affiche plus "bin\\ollama.exe serve"
    quand seul un Ollama système a été détecté par setup_ollama() (le binaire
    portable n'existe alors pas encore sur la clé, la commande échouerait).
    """
    if ollama_portable_path is None:
        ollama_portable_path = _portable_ollama_path()

    print()
    print(cyan("====================================================="))
    print(green("  Installation terminee !"))
    print(cyan("====================================================="))
    print()
    print("  Interface web integree (API) : http://localhost:8000")
    print("  OpenWebUI (interface avancee): http://localhost:3000")
    print("  Documentation API             : http://localhost:8000/docs")
    print()
    print("  Prochaines etapes :")
    print()
    if SYSTEM == "windows":
        if ollama_portable_path:
            print(yellow("  1. Lancer Ollama :  bin\\ollama.exe serve   (portable, sur la cle)"))
        else:
            print(yellow("  1. Lancer Ollama :  (auto — telecharge au 1er lancement de"))
            print(yellow("                       launchers\\JARVIS.bat, jamais sur l'ordi)"))
        print(yellow("  2. JARVIS Core   :  launchers\\JARVIS.bat"))
    else:
        if ollama_portable_path:
            print(yellow(f"  1. Lancer Ollama :  {ollama_portable_path} serve   (portable)"))
        else:
            print(yellow("  1. Lancer Ollama :  (auto — telecharge au 1er lancement,"))
            print(yellow("                       jamais installe sur le systeme)"))
        print(yellow("  2. JARVIS Core   :  ./launchers/jarvis.sh"))
    print()


def main():
    """Main."""
    header()

    results = []
    results.append(install_python_deps())
    results.append(setup_ollama())

    if all(results):
        print_final()
    else:
        success = sum(results)
        total = len(results)
        print(f"\n  {yellow(f'{success}/{total} etapes reussies')}")
        print(gray("  Relancez le script apres avoir corrige les erreurs."))


if __name__ == "__main__":
    main()
