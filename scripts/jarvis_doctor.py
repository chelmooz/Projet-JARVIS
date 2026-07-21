#!/usr/bin/env python3
"""jarvis doctor — Script de diagnostic des prérequis JARVIS.

Vérifie l'environnement local (Python, .env, binaire Ollama, modèles, port)
et rapporte un résumé lisible. Ne modifie rien : outil de diagnostic pur.

Usage : python scripts/jarvis_doctor.py
"""
import os
import sys

from config.paths import MODELS_OLLAMA, OLLAMA_HOST, ROOT
from services.system import get_ollama_path


def _check_python() -> tuple[bool, str]:
    """Vérifie la version de Python (>=3.10 recommandé)."""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    return ok, f"Python {major}.{minor}"


def _check_env_file() -> tuple[bool, str]:
    """Vérifie la présence de .env (optionnel mais recommandé)."""
    env = os.path.join(ROOT, ".env")
    if os.path.exists(env):
        return True, ".env present"
    return False, ".env absent (cp .env.example .env recommande)"


def _check_ollama_binary() -> tuple[bool, str]:
    """Vérifie que le binaire Ollama portable est présent ou installable."""
    path = get_ollama_path()
    if path and os.path.exists(path):
        return True, f"Ollama trouve: {path}"
    return False, "Ollama absent (telecharge automatiquement au 1er lancement)"


def _check_models_dir() -> tuple[bool, str]:
    """Vérifie le répertoire des modèles Ollama."""
    if os.path.isdir(MODELS_OLLAMA):
        return True, f"Dossier modeles: {MODELS_OLLAMA}"
    return False, f"Dossier modeles absent: {MODELS_OLLAMA} (cree au 1er pull)"


def _check_port() -> tuple[bool, str]:
    """Vérifie que le port Ollama (11436) n'est pas déjà occupé par un tiers."""
    import socket

    host, _, port_s = OLLAMA_HOST.partition(":")
    port = int(port_s)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        # Si quelque chose ecoute deja, ca peut etre Ollama lui-meme (ok) ou un
        # conflit. On signale juste l'etat pour information.
        result = s.connect_ex((host, port))
    if result == 0:
        return True, f"Port {port} deja en ecoute (Ollama actif ou conflit possible)"
    return True, f"Port {port} libre"


CHECKS = [
    ("Python", _check_python),
    ("Fichier .env", _check_env_file),
    ("Binaire Ollama", _check_ollama_binary),
    ("Dossier modeles", _check_models_dir),
    ("Port Ollama", _check_port),
]


def run_checks() -> list[tuple[str, bool, str]]:
    """Exécute tous les checks et retourne [(nom, ok, detail), ...]."""
    results = []
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:  # pragma: no cover - diagnostic ne doit jamais planter
            ok, detail = False, f"Erreur: {e}"
        results.append((name, ok, detail))
    return results


def main() -> int:
    """Point d'entrée : affiche le rapport et retourne 0 si tout est OK."""
    print("JARVIS doctor — diagnostic de l'environnement")
    print("=" * 50)
    results = run_checks()
    all_ok = True
    for name, ok, detail in results:
        status = "OK " if ok else "WARN"
        if not ok:
            all_ok = False
        print(f"  [{status}] {name:18} {detail}")
    print("=" * 50)
    if all_ok:
        print("Environnement pret.")
        return 0
    print("Des elements sont a verifier (voir ci-dessus).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
