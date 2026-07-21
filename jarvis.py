#!/usr/bin/env python3
"""JARVIS Portable — Point d'entrée unique (Composition Root).

Responsabilité unique : pre-flight, démarrage Ollama, lancement Uvicorn natif.
Fail-Fast strict : toute dépendance critique manquante → exit(1).
Uvicorn gère nativement SIGINT/SIGTERM. Le bloc `finally` garantit
l'arrêt propre du processus Ollama enfant.
"""
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

from config.bootstrap import ensure_project_root
from config.constants import DEFAULT_MODEL, JARVIS_PORT, VERSION
from config.paths import OLLAMA_PORT
from services.launcher import ProcessManager
from services.ollama_installer import ensure_ollama_binary
from services.system import BASE_DIR, SYSTEM

_PROJECT_ROOT = ensure_project_root()
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def setup_logging() -> logging.Logger:
    """Configure le logger de démarrage. Pas de dépendance circulaire."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("JARVIS")


def print_banner(logger: logging.Logger) -> None:
    """Affiche les informations de démarrage via le logger."""
    logger.info("=" * 60)
    logger.info("  JARVIS Portable Edition v%s", VERSION)
    logger.info("  Interface : http://127.0.0.1:%d", JARVIS_PORT)
    logger.info("  Modèle par défaut : %s", DEFAULT_MODEL)
    logger.info("  API Status  : http://127.0.0.1:%d/api/status", JARVIS_PORT)
    logger.info("=" * 60)
    logger.info("  [Ctrl+C] pour arrêter proprement tous les services")


def preflight_check(logger: logging.Logger) -> bool:
    """Vérifie et provisionne les dépendances critiques. Fail-Fast."""
    logger.info("Vérification du binaire Ollama portable...")
    ollama_bin = ensure_ollama_binary(logger)

    if not ollama_bin or not os.path.exists(ollama_bin):
        logger.critical(
            "ÉCHEC CRITIQUE : Le binaire Ollama est introuvable.\n"
            "Exécutez : 'python scripts/install.py'\n"
            "ou vérifiez votre connexion Internet pour le téléchargement initial."
        )
        return False

    logger.info("Binaire Ollama trouvé : %s", ollama_bin)
    return True


def main() -> None:
    """Point d'entrée principal."""
    os.chdir(BASE_DIR)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

    logger = setup_logging()
    logger.info("=== Démarrage de JARVIS Portable ===")
    logger.info("Système : %s | Python : %s", SYSTEM, sys.version.split()[0])
    logger.info("Répertoire de travail : %s", BASE_DIR)

    if not preflight_check(logger):
        sys.exit(1)

    pm = ProcessManager()

    logger.info("Démarrage du moteur Ollama sur le port %d...", OLLAMA_PORT)
    if not pm.start_ollama():
        logger.critical("Échec du démarrage d'Ollama. Consultez logs/ollama.log.")
        pm.stop_all()
        sys.exit(1)

    print_banner(logger)

    if not os.environ.get("JARVIS_NO_BROWSER"):
        try:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{JARVIS_PORT}")
        except Exception:
            pass

    try:
        logger.info("Lancement du serveur API sur http://127.0.0.1:%d", JARVIS_PORT)
        uvicorn.run(
            "controllers.router:app",
            host="127.0.0.1",
            port=JARVIS_PORT,
            log_level="info",
            reload=False,
        )
    finally:
        logger.info("Arrêt du serveur API. Nettoyage des processus enfants...")
        pm.stop_all()


if __name__ == "__main__":
    main()
