#!/usr/bin/env python3
"""
JARVIS Portable Edition — Installateur multi-OS
Detecte automatiquement Windows / Linux / macOS.
Installe les dependances Python, Ollama et OpenWebUI.
"""

import os
import platform
import shutil
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
    os.system("cls" if SYSTEM == "windows" else "clear")
    print(cyan("====================================================="))
    print(cyan("  JARVIS Portable Edition v5.4"))
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
    """Detecte l'OS et propose l'installation d'Ollama."""
    print(yellow("\n[2/3] Ollama (moteur d'inference)..."))

    if shutil.which("ollama"):
        print(f"  {green('[OK]')} Ollama deja installe")
        return True

    print(gray("  Necessite ~680 Mo sur le disque."))

    try:
        if sys.stdin.isatty():
            resp = input(gray("  Installer Ollama ? [y/N] ")).strip().lower()
            if resp != "y":
                print(gray("  Ignore. Installation manuelle :"))
                if SYSTEM in ("linux", "darwin"):
                    print(cyan("    curl -fsSL https://ollama.com/install.sh | sh"))
                else:
                    print(cyan("    irm https://ollama.com/install.ps1 | iex"))
                return False
    except (EOFError, KeyboardInterrupt):
        return False

    print(f"  Detection : {SYSTEM}")
    if SYSTEM == "windows":
        print(cyan("    irm https://ollama.com/install.ps1 | iex"))
        print(gray("  Lancez cette commande dans PowerShell en administrateur."))
        return False
    elif SYSTEM in ("linux", "darwin"):
        print(cyan("    curl -fsSL https://ollama.com/install.sh | sh"))
        try:
            subprocess.run(
                ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                check=True, timeout=120
            )
            print(f"  {green('[OK]')} Ollama installe")
            return True
        except Exception as e:
            print(red(f"  Erreur: {e}"))
            print(gray("  Installez manuellement : curl -fsSL https://ollama.com/install.sh | sh"))
            return False
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


def print_final():
    """Print final."""
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
        print(yellow("  1. Lancer Ollama :  bin\\ollama.exe serve"))
        print(yellow("  2. JARVIS Core   :  launchers\\JARVIS.bat"))
    else:
        print(yellow("  1. Lancer Ollama :  ollama serve"))
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
