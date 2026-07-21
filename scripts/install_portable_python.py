#!/usr/bin/env python3
"""
JARVIS Portable — Setup script for portable Python
Telecharge et configure un Python 3.12 portable sur la cle USB.
Usage : python install_portable_python.py
"""
import os
import subprocess
import sys
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTABLE_DIR = os.path.join(BASE_DIR, "portable_python", "win")
VENV_DIR = os.path.join(BASE_DIR, "venv")
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")

PYTHON_URLS = {
    "win32": (
        "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
        "python-3.12.10-embed-amd64.zip"
    ),
}


def log(msg, ok=True):
    """Log."""
    print(f"  {'OK' if ok else '**'} {msg}")


def download(url, dest):
    """Download."""
    log(f"Telechargement {url.split('/')[-1]}...")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        log(f"Echec : {e}", False)
        return False


def extract(zip_path, target):
    """Extract."""
    log(f"Extraction vers {target}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target)


def enable_site_packages(python_dir):
    """Enable site packages."""
    for f in os.listdir(python_dir):
        if f.endswith("._pth"):
            path = os.path.join(python_dir, f)
            with open(path) as fh:
                content = fh.read()
            modified = content.replace("#import site", "import site")
            if "DLLs" not in content:
                modified += "\n.\\DLLs\n.\\Scripts\n"
            if "..\\.." not in modified:
                modified += "..\\..\n"
            with open(path, "w") as fh:
                fh.write(modified)
            log(f"Active site-packages dans {f}")
            dlls = os.path.join(python_dir, "DLLs")
            if not os.path.exists(dlls):
                os.makedirs(dlls)
            return True
    log("Fichier ._pth introuvable", False)
    return False


def install_pip(python_exe):
    """Install pip."""
    log("Installation de pip...")
    get_pip = os.path.join(BASE_DIR, "get-pip.py")
    url = "https://bootstrap.pypa.io/get-pip.py"
    try:
        urllib.request.urlretrieve(url, get_pip)
    except Exception:
        log("Impossible de telecharger get-pip.py", False)
        return False
    r = subprocess.run([python_exe, get_pip], capture_output=True, text=True)
    os.remove(get_pip)
    if r.returncode != 0:
        log(f"Echec pip : {r.stderr.strip()}", False)
        return False
    log("pip installe")
    return True


def create_venv(python_exe):
    """Create venv."""
    log(f"Creation du venv dans {VENV_DIR}...")
    r = subprocess.run([python_exe, "-m", "venv", VENV_DIR], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"Echec venv : {r.stderr.strip()}", False)
        return False
    log("OK")
    return True


def install_requirements():
    """Install requirements."""
    log("Installation des dependances...")
    pip = os.path.join(VENV_DIR, "Scripts", "python.exe")
    r = subprocess.run(
        [pip, "-m", "pip", "install", "--quiet", "-r", REQUIREMENTS],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        log(f"Echec : {r.stderr.strip()}", False)
        return False
    log("OK")
    return True


def main():
    """Main."""
    print()
    print("  JARVIS Portable — Installation de Python portable")
    print()

    if os.name != "nt":
        print("  Ce script est pour Windows uniquement.")
        print("  Sur Linux/Mac, utilisez le Python systeme ou installez-le via votre gestionnaire de paquets.")
        sys.exit(1)

    if os.path.exists(os.path.join(PORTABLE_DIR, "python.exe")):
        log("Python portable deja installe dans portable_python/win/")
    else:
        os.makedirs(PORTABLE_DIR, exist_ok=True)
        osname = "win32"
        url, zipname = PYTHON_URLS[osname]
        zippath = os.path.join(BASE_DIR, zipname)

        if not os.path.exists(zippath) and not download(url, zippath):
                sys.exit(1)

        extract(zippath, PORTABLE_DIR)
        os.remove(zippath)
        log("Extraction terminee")

        enable_site_packages(PORTABLE_DIR)
        python_exe = os.path.join(PORTABLE_DIR, "python.exe")

        if not install_pip(python_exe):
            sys.exit(1)

        log("Python portable pret dans portable_python/win/")

    print()
    log("Creation du venv...")
    python_exe = os.path.join(PORTABLE_DIR, "python.exe")
    if not os.path.exists(VENV_DIR) and not create_venv(python_exe):
            sys.exit(1)

    log("Installation des dependances...")
    if not install_requirements():
        sys.exit(1)

    print()
    print("=" * 58)
    print("  Installation terminee !")
    print(f"  Python portable : {PORTABLE_DIR}")
    print(f"  Environnement   : {VENV_DIR}")
    print("  Lancement       : double-clic sur JARVIS.bat")
    print("=" * 58)
    print()


if __name__ == "__main__":
    main()
