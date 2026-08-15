#!/usr/bin/env python3
"""
JARVIS Portable — Vendoring des wheels (installation offline).
Telecharge les distributions multi-plateforme dans vendor_wheels/ a partir de
requirements.lock (epingle par uv export, source unique de verite).

Usage : python scripts/vendor_wheels.py [--platform PLATFORMS...]

Par defaut : win_amd64, manylinux_2_17_x86_64, macosx_11_0_arm64 (Python 3.12,
binaires uniquement). Le dossier vendor_wheels/ est ignore de git (trop lourd
pour le depot : ~500 Mo cumules) et produit sur la cle de deploiement.

Procede valide (pip 26+) :
  1. wheels : pip download -r requirements.lock --no-deps --only-binary=:all:
     (requirements.lock est plat et complet, pas besoin du resolver de deps ;
      --no-deps est impose par pip des qu'on croise --platform/--python-version)
  2. sdist exception : antlr4-python3-runtime==4.9.3 n'a pas de wheel (omegaconf
     l'epingle en ==4.9.*) -> telecharge dans vendor_wheels/ comme sdist source
     (pur Python, installe avec setuptools present dans le Python portable).
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.lock")
VENDOR_DIR = os.path.join(BASE_DIR, "vendor_wheels")
PYTHON_VERSION = "3.12"

DEFAULT_PLATFORMS = [
    "win_amd64",
    "linux_x86_64",
    "macosx_10_15_x86_64",
    "macosx_11_0_arm64",
]

# Paquets sans wheel (sdist uniquement), telecharges a part en mode source.
SDIST_ONLY = ["antlr4-python3-runtime==4.9.3"]


def color(text, code):
    """Color."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(text):
    return color(text, "92")


def yellow(text):
    return color(text, "93")


def red(text):
    return color(text, "91")


def _filtered_requirements(dest, exc):
    """Recopie requirements.lock sans les paquets en exception, pour pip download."""
    filtered = os.path.join(dest, "requirements.vendor.txt")
    with open(REQUIREMENTS, encoding="utf-8") as src, open(filtered, "w", encoding="utf-8") as out:
        for line in src:
            if any(pkg.split("==")[0] in line for pkg in exc):
                continue
            if line and not line.startswith("#"):
                out.write(line.split("# via", 1)[0].rstrip() + "\n")
    return filtered


def _download_platform_wheel(platform_tag, requirements_file, dest):
    """Telecharge les wheels binaires pour une plateforme donnee (--no-deps)."""
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "-r",
        requirements_file,
        "-d",
        dest,
        "--platform",
        platform_tag,
        "--python-version",
        PYTHON_VERSION,
        "--only-binary=:all:",
        "--no-deps",
    ]
    print(yellow(f"\n[{platform_tag}] wheels -> {dest}"))
    try:
        subprocess.run(cmd, check=True, timeout=1200)
        print(f"  [OK] {platform_tag} wheels")
        return True
    except subprocess.CalledProcessError as e:
        print(red(f"  Echec wheels {platform_tag} (retour {e.returncode})"))
        return False


def download_wheels(platform_tag, dest, requirements_file):
    """Telecharge les wheels binaires pour une plateforme (--no-deps)."""
    return _download_platform_wheel(platform_tag, requirements_file, dest)


def download_sdist_exceptions(dest):
    """Telecharge les sdists sans wheel (antlr4) une seule fois (pur Python)."""
    ok = True
    for pkg in SDIST_ONLY:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            pkg,
            "-d",
            dest,
            "--no-deps",
            "--no-binary=:all:",
        ]
        print(yellow(f"\n[sdist] {pkg} -> {dest}"))
        try:
            subprocess.run(cmd, check=True, timeout=600)
            print(f"  {green(f'[OK] {pkg}')}")
        except subprocess.CalledProcessError as e:
            print(red(f"  Echec {pkg} (retour {e.returncode})"))
            ok = False
    return ok


def main():
    """Main."""
    print()
    print("  JARVIS Portable — Vendoring des wheels")
    print()

    args = sys.argv[1:]
    if args and args[0] == "--platform":
        args = args[1:]
    platforms = args
    if not platforms:
        platforms = DEFAULT_PLATFORMS
        print(f"  Plateformes par defaut : {', '.join(platforms)}")
    else:
        print(f"  Plateformes : {', '.join(platforms)}")

    if not os.path.exists(REQUIREMENTS):
        print(red(f"  requirements.lock introuvable : {REQUIREMENTS}"))
        print(red("  Regenerer : uv export --format requirements-txt --no-hashes --no-emit-project"))
        sys.exit(1)

    os.makedirs(VENDOR_DIR, exist_ok=True)
    requirements_file = _filtered_requirements(VENDOR_DIR, SDIST_ONLY)

    results = []
    for tag in platforms:
        dest = os.path.join(VENDOR_DIR, tag)
        os.makedirs(dest, exist_ok=True)
        results.append(download_wheels(tag, dest, requirements_file))

    assert download_sdist_exceptions(VENDOR_DIR)
    ok = sum(results)

    if ok == len(platforms):
        print(f"\n  {green('Vendoring termine.')}")
        print(f"  Dossier  : {VENDOR_DIR}")
        print("  Poids    : ~500 Mo pour 3 plateformes (non versione dans git).")
        print("  install.py --offline : pip install --no-index --find-links vendor_wheels")
    else:
        print(f"\n  {red(f'{ok}/{len(platforms)} plateformes reussies')}")
        print(red("  Verifiez le reseau ou les logs ci-dessus."))
        sys.exit(1)


if __name__ == "__main__":
    main()
