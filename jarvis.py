#!/usr/bin/env python3
"""JARVIS Portable — Point d'entrée unique (Composition Root).

Refacto DevOps / SOLID / KISS :
- Responsabilité unique : Vérification pré-vol (pre-flight), démarrage d'Ollama, 
  et lancement natif d'Uvicorn (plus de subprocess Popen pour l'API).
- Fail-Fast strict : Si une dépendance critique (Ollama) échoue, le programme s'arrête 
  immédiatement avec un code d'erreur (exit 1). Pas d'état dégradé silencieux.
- Gestion propre des signaux : Uvicorn gère nativement SIGINT/SIGTERM. Le bloc `finally` 
  garantit l'arrêt propre du processus Ollama enfant.
"""
import logging
import os
import signal
import sys
import webbrowser

import uvicorn
from dotenv import load_dotenv

from config.bootstrap import ensure_project_root
from config.constants import DEFAULT_MODEL, JARVIS_PORT, VERSION
from config.paths import OLLAMA_PORT
from services.launcher import ProcessManager
from services.ollama_installer import ensure_ollama_binary
from services.system import BASE_DIR, SYSTEM

# --- Configuration ---
# Le projet_root est garanti par le bootstrap
_PROJECT_ROOT = ensure_project_root()

# Charger les variables d'environnement en premier
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def setup_logging() -> logging.Logger:
    """Configure un logger standard, lisible et sans dépendance circulaire."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # Optionnel : ajouter un FileHandler si la persistance des logs de démarrage est critique
            # logging.FileHandler(os.path.join(BASE_DIR, "logs", "jarvis_startup.log"), encoding="utf-8")
        ]
    )
    return logging.getLogger("JARVIS")


def print_banner():
    """Affiche les informations de démarrage de manière claire."""
    print("\n" + "=" * 60)
    print(f"  JARVIS Portable Edition v{VERSION}")
    print(f"  Interface : http://127.0.0.1:{JARVIS_PORT}")
    print(f"  Modèle par défaut : {DEFAULT_MODEL}")
    print(f"  API Status  : http://127.0.0.1:{JARVIS_PORT}/api/status")
    print("=" * 60)
    print("  [Ctrl+C] pour arrêter proprement tous les services\n")


def preflight_check(logger: logging.Logger) -> bool:
    """Vérifie et provisionne les dépendances critiques avant tout démarrage.
    
    Retourne True si tout est prêt, False sinon.
    """
    logger.info("Vérification du binaire Ollama portable...")
    
    # ensure_ollama_binary doit retourner le chemin du binaire ou None
    ollama_bin = ensure_ollama_binary(logger)
    
    if not ollama_bin or not os.path.exists(ollama_bin):
        logger.critical(
            "ÉCHEC CRITIQUE : Le binaire Ollama est introuvable.\n"
            "Veuillez exécuter le script d'installation : 'python scripts/install.py'\n"
            "ou vérifier votre connexion Internet pour le téléchargement initial."
        )
        return False
        
    logger.info("Binaire Ollama trouvé : %s", ollama_bin)
    return True


def main():
    """Point d'entrée principal de l'application."""
    # 1. Initialisation de l'environnement
    os.chdir(BASE_DIR)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    
    logger = setup_logging()
    logger.info("=== Démarrage de JARVIS Portable ===")
    logger.info("Système : %s | Python : %s", SYSTEM, sys.version.split()[0])
    logger.info("Répertoire de travail : %s", BASE_DIR)

    # 2. Pre-flight check (Fail-Fast)
    if not preflight_check(logger):
        sys.exit(1)

    # 3. Initialisation du gestionnaire de processus (uniquement pour Ollama)
    pm = ProcessManager()

    # 4. Gestion propre des signaux d'arrêt (Graceful Shutdown)
    def cleanup_handler(signum, frame):
        logger.info("\nSignal d'arrêt reçu (%d). Nettoyage en cours...", signum)
        pm.stop_all()
        logger.info("Arrêt terminé. À bientôt.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup_handler)

    # 5. Démarrage du moteur d'inférence (Ollama)
    # Le nouveau ProcessManager inclut déjà un health-check avec backoff exponentiel.
    # Plus besoin de time.sleep(3) arbitraire ici.
    logger.info("Démarrage du moteur Ollama sur le port %d...", OLLAMA_PORT)
    if not pm.start_ollama():
        logger.critical("Échec du démarrage d'Ollama. Consultez logs/ollama.log pour les détails.")
        pm.stop_all()
        sys.exit(1)

    # 6. Lancement de l'API FastAPI (Uvicorn)
    # KISS / DevOps : Uvicorn est exécuté de manière native dans le thread principal.
    # Il gère lui-même les signaux, le pool de travailleurs et le graceful shutdown.
    # C'est infiniment plus robuste que de le lancer via subprocess.Popen.
    print_banner()
    
    # Ouverture du navigateur (silencieuse en cas d'échec, ex: environnement headless)
    try:
        webbrowser.open(f"http://127.0.0.1:{JARVIS_PORT}")
    except Exception:
        pass  # Ignoré : ne doit pas bloquer le démarrage en CLI/SSH

    try:
        logger.info("Lancement du serveur API sur http://127.0.0.1:%d", JARVIS_PORT)
        uvicorn.run(
            "controllers.router:app",
            host="127.0.0.1",
            port=JARVIS_PORT,
            log_level="info",
            reload=False,  # Mode production (portable)
        )
    finally:
        # Ce bloc s'exécute toujours, même en cas d'exception non gérée dans Uvicorn
        # ou lors d'un arrêt propre via Ctrl+C.
        logger.info("Arrêt du serveur API. Nettoyage des processus enfants...")
        pm.stop_all()


if __name__ == "__main__":
    main()
