#!/usr/bin/env python3
"""Launcher Windows — Point d'entrée unifié pour JARVIS sur Windows.

Gère :
- Chargement .env via python-dotenv (déjà utilisé côté Python)
- Affichage + log simultané (tee)
- Propagation des signaux (Ctrl+C, Ctrl+Break)
- Gestion propre du cycle de vie Ollama + Uvicorn
- Feedback console visible pendant les opérations longues (bootstrap, Ollama install/start)
"""

import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from config.bootstrap import ensure_project_root
from config.constants import DEFAULT_MODEL, JARVIS_PORT, VERSION
from config.paths import OLLAMA_PORT
from services.dependency_bootstrap import bootstrap_dependencies
from services.launcher import ProcessManager, wait_for_port_free
from services.log_adapter import to_step_logger
from services.ollama_installer import ensure_ollama_binary
from services.port_manager import kill_existing
from services.system import BASE_DIR, SYSTEM

_PROJECT_ROOT = ensure_project_root()


class ConsoleProgress:
    """Affiche une animation de progression dans la console."""

    def __init__(self, message: str, logger: logging.Logger) -> None:
        self._message = message
        self._logger = logger
        self._running = False
        self._thread: threading.Thread | None = None
        self._chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def start(self) -> None:
        """Démarre l'animation."""
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True, final_message: str | None = None) -> None:
        """Arrête l'animation."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if final_message:
            if success:
                self._logger.info(final_message)
            else:
                self._logger.error(final_message)
        else:
            status = "✓" if success else "✗"
            self._logger.info(f"{status} {self._message}")

    def _animate(self) -> None:
        idx = 0
        while self._running:
            char = self._chars[idx % len(self._chars)]
            sys.stdout.write(f"\r{char} {self._message}...")
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1
        # Efface la ligne d'animation
        sys.stdout.write("\r" + " " * (len(self._message) + 10) + "\r")
        sys.stdout.flush()


def setup_logging() -> logging.Logger:
    """Configure le logger de démarrage."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Assure la reconfiguration même si déjà fait
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

    progress = ConsoleProgress("Téléchargement/Vérification Ollama", logger)
    progress.start()

    ollama_bin = ensure_ollama_binary(to_step_logger(logger))

    progress.stop(success=bool(ollama_bin))

    if not ollama_bin or not os.path.exists(ollama_bin):
        logger.critical(
            "ÉCHEC CRITIQUE : Le binaire Ollama est introuvable.\n"
            "Exécutez : 'python scripts/install.py'\n"
            "ou vérifiez votre connexion Internet pour le téléchargement initial."
        )
        return False

    logger.info("Binaire Ollama trouvé : %s", ollama_bin)
    return True


def _shutdown(pm: ProcessManager, signum: int, frame: object) -> None:
    """Gestionnaire de signal pour l'arrêt propre (SIGINT/SIGTERM/Ctrl+Break)."""
    logger = logging.getLogger("JARVIS")
    logger.info("Signal %s reçu. Arrêt en cours...", signum)
    try:
        pm.stop_all()
    except Exception:
        logger.warning("Erreur lors de l'arrêt des processus", exc_info=True)
    sys.exit(0)


def run_with_progress(
    func: Callable[[], Any],
    message: str,
    logger: logging.Logger,
) -> Any:
    """Exécute une fonction avec une animation de progression."""
    progress = ConsoleProgress(message, logger)
    progress.start()
    try:
        result = func()
        progress.stop(success=True)
        return result
    except Exception as e:
        progress.stop(success=False, final_message=f"✗ {message} — ÉCHEC : {e}")
        raise


def main() -> None:
    """Point d'entrée principal Windows."""
    os.chdir(BASE_DIR)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

    logger = setup_logging()
    logger.info("=== Démarrage de JARVIS Portable (Windows) ===")
    logger.info("Système : %s | Python : %s", SYSTEM, sys.version.split()[0])
    logger.info("Répertoire de travail : %s", BASE_DIR)

    # Charger .env via python-dotenv (source unique avec jarvis.py)
    import dotenv

    dotenv.load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

    logger.info("Provisionnement des dépendances Python...")
    run_with_progress(lambda: bootstrap_dependencies(logger), "Installation dépendances Python", logger)

    # Imports différés : sûrs uniquement après bootstrap_dependencies().
    import uvicorn

    if not preflight_check(logger):
        sys.exit(1)

    pm = ProcessManager()

    logger.info("Démarrage du moteur Ollama sur le port %d...", OLLAMA_PORT)
    if not run_with_progress(pm.start_ollama, f"Démarrage Ollama (port {OLLAMA_PORT})", logger):
        logger.critical("Échec du démarrage d'Ollama. Consultez logs/ollama.log.")
        pm.stop_all()
        sys.exit(1)

    print_banner(logger)

    # Gestionnaires de signaux Windows (Ctrl+C, Ctrl+Break)
    signal.signal(signal.SIGINT, lambda s, f: _shutdown(pm, s, f))
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda s, f: _shutdown(pm, s, f))

    # Vérification du port JARVIS
    logger.info("Vérification du port JARVIS (%d)...", JARVIS_PORT)
    kill_existing("jarvis", JARVIS_PORT)
    if not run_with_progress(
        lambda: wait_for_port_free("127.0.0.1", JARVIS_PORT),
        f"Libération port {JARVIS_PORT}",
        logger,
    ):
        logger.critical(
            "Le port %d est toujours occupé après tentative de libération. "
            "Veuillez fermer l'application qui l'utilise ou définir JARVIS_PORT dans .env.",
            JARVIS_PORT,
        )
        pm.stop_all()
        sys.exit(1)

    # Port confirmé libre → ouvrir le navigateur
    if not os.environ.get("JARVIS_NO_BROWSER"):
        try:
            import webbrowser

            webbrowser.open(f"http://127.0.0.1:{JARVIS_PORT}")
        except Exception:
            logger.info("Impossible d'ouvrir le navigateur automatiquement")

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
