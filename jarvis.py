#!/usr/bin/env python3
"""JARVIS Portable — Entry point unique. Plug & play."""
import argparse
import contextlib
import logging
import os
import signal
import sys
import time
import webbrowser

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from config.bootstrap import ensure_project_root

_PROJECT_ROOT = ensure_project_root()

# Charger .env AVANT config.constants
if load_dotenv is not None:
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

try:
    from config.constants import DEFAULT_BACKEND, DEFAULT_MODEL, JARVIS_PORT, VERSION
    from config.paths import OLLAMA_PORT
    from services.launcher import ProcessManager, wait_for
    from services.log import LogService
    from services.ollama_installer import ensure_ollama_binary
    from services.system import BASE_DIR, SYSTEM, ensure_venv
except ImportError as e:
    sys.stderr.write(
        "Erreur: modules JARVIS introuvables.\n"
        "Lancez jarvis.py depuis la racine du projet.\n"
        f"Detail: {e}\n"
    )
    sys.exit(1)

# --- Constantes ---
OLLAMA_SYSTEM_PORT = 11434
OLLAMA_WAIT = 3
OLLAMA_TIMEOUT = 90
CORE_WAIT = 2


def setup_logging() -> logging.Logger:
    """Configure et retourne le logger standard (élimine le besoin d'un wrapper custom)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger("JARVIS")


def log_status(logger: logging.Logger, svc: str, msg: str, ok: bool = True):
    """Log formaté pour la console et le fichier, sans état global."""
    status = "OK" if ok else "**"
    logger.info(f"[{svc}] {status} {msg}")


def print_banner(info: dict):
    be = info.get("backend", DEFAULT_BACKEND)
    print("\n" + "=" * 58)
    print(f"  JARVIS Portable Edition v{VERSION}")
    print(f"  Interface : http://localhost:{JARVIS_PORT}")
    if info.get("openwebui"):
        print("  OpenWebUI : http://localhost:3000")
    print(f"  Backend   : {be.upper()} ({DEFAULT_MODEL})")
    print(f"  API       : http://localhost:{JARVIS_PORT}/api/jarvis")
    print(f"  Statut    : http://localhost:{JARVIS_PORT}/api/status")
    print("=" * 58)
    print("  Ctrl+C pour tout arreter\n")


def parse_args():
    parser = argparse.ArgumentParser(description="JARVIS Portable Edition")
    parser.add_argument("--diag", action="store_true", help="Afficher le diagnostic systeme et quitter")
    return parser.parse_args()


def start_ollama_backend(pm: ProcessManager, logger: logging.Logger) -> str:
    log_status(logger, "Ollama", "Demarrage force du binaire portable...")
    
    # Injection du logger via une lambda pour respecter la signature attendue
    ollama_bin = ensure_ollama_binary(lambda svc, msg, ok=True: log_status(logger, svc, msg, ok))
    
    if not ollama_bin:
        log_status(logger, "Ollama", "Installation impossible", ok=False)
        return "absent"
        
    pm.start_ollama()
    time.sleep(OLLAMA_WAIT)
    
    if wait_for(f"http://localhost:{OLLAMA_PORT}/api/tags", "Ollama", 
                lambda svc, msg, ok=True: log_status(logger, svc, msg, ok), 
                timeout=OLLAMA_TIMEOUT):
        return DEFAULT_BACKEND
        
    log_status(logger, "Ollama", "Echec demarrage", ok=False)
    return "echec"


def start_core_services(pm: ProcessManager, python: str, logger: logging.Logger) -> dict:
    log_status(logger, "JARVIS", "Demarrage du core API...")
    pm.start_jarvis(python)
    time.sleep(CORE_WAIT)
    pm.start_openwebui(python)
    
    jarvis_ok = wait_for(f"http://localhost:{JARVIS_PORT}/api/status", "JARVIS Core", 
                         lambda svc, msg, ok=True: log_status(logger, svc, msg, ok))
    owui_ok = pm.has_service("OpenWebUI") and wait_for("http://localhost:3000", "OpenWebUI", 
                                                       lambda svc, msg, ok=True: log_status(logger, svc, msg, ok))
    return {"jarvis": jarvis_ok, "openwebui": owui_ok}


def run_diag():
    from services.diagnostic import DiagnosticService
    d = DiagnosticService()
    d.run_full()
    d.print_report()


def shutdown(pm: ProcessManager, signum, frame):
    print("  A bientot.")
    try:
        pm.stop_all()
    finally:
        sys.exit(0)


def main():
    os.chdir(BASE_DIR)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    
    # Composition Root du launcher : instanciation explicite des dépendances
    logger = setup_logging()
    pm = ProcessManager()

    signal.signal(signal.SIGINT, lambda s, f: shutdown(pm, s, f))
    if hasattr(signal, "SIGTERM"):
        with contextlib.suppress(ValueError):
            signal.signal(signal.SIGTERM, lambda s, f: shutdown(pm, s, f))

    logger.info("=== JARVIS demarrage ===")
    print(f"\n  JARVIS Portable Edition v{VERSION}")
    print(f"  OS : {SYSTEM}")
    print(f"  Python : {sys.version.split()[0]}")
    print(f"  Repertoire : {BASE_DIR}\n")

    python = ensure_venv(lambda svc, msg, ok=True: log_status(logger, svc, msg, ok))
    log_status(logger, "Init", f"Python : {python}")

    backend = start_ollama_backend(pm, logger)
    svc_info = start_core_services(pm, python, logger)

    info = {"backend": backend, **svc_info}
    print_banner(info)
    
    with contextlib.suppress(Exception):
        webbrowser.open(f"http://localhost:{JARVIS_PORT}")
        
    pm.monitor()


if __name__ == "__main__":
    args = parse_args()
    if args.diag:
        run_diag()
    else:
        main()
