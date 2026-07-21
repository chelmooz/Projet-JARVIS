#!/usr/bin/env python3
"""JARVIS Portable — Entry point unique. Plug & play."""
import argparse
import contextlib
import os
import signal
import sys
import time
import webbrowser

try:
    from dotenv import load_dotenv
except Exception:  # python-dotenv optionnel au demarrage
    load_dotenv = None

from config.bootstrap import ensure_project_root

_PROJECT_ROOT = ensure_project_root()

# Charger .env AVANT config.constants : ce dernier lit os.environ a l'import
# (JARVIS_PORT, JARVIS_LOG_LEVEL...). Sans cela, ces valeurs .env sont ignorees
# quand on lance `python jarvis.py` directement (hors launchers qui setent deja
# l'environnement). load_dotenv ne surcharge pas les variables deja posees.
if load_dotenv is not None:
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

try:
    from config.constants import DEFAULT_BACKEND, DEFAULT_MODEL, JARVIS_PORT, VERSION
    from config.paths import OLLAMA_PORT
    from services.launcher import ProcessManager, wait_for
    from services.log import LogService
    from services.ollama_installer import ensure_ollama_binary
    from services.system import BASE_DIR, SYSTEM, ensure_venv
except ImportError as _imp_err:
    sys.stderr.write(
        "Erreur: modules JARVIS introuvables.\n"
        "Lancez jarvis.py depuis la racine du projet (dossier Projet-JARVIS sur la clef USB).\n"
        f"Detail: {_imp_err}\n"
    )
    raise

# --- Constantes ---
# OLLAMA_PORT est la source unique (config/paths.py) : pas de redefinition locale
# pour eviter la derive de port entre le launcher et l'adapter Ollama.
OLLAMA_SYSTEM_PORT = 11434
OLLAMA_WAIT = 3
OLLAMA_TIMEOUT = 90
CORE_WAIT = 2

# Logger lazy (pas d'initialisation au niveau module)
_log_svc = None


def _get_log_svc():
    global _log_svc
    if _log_svc is None:
        _log_svc = LogService()
    return _log_svc


def log(svc, msg, ok=True):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{svc}] {'OK' if ok else '**'} {msg}"
    print(f"  {line}")
    _get_log_svc().log("INFO", line)


def print_banner(info):
    be = info.get("backend", DEFAULT_BACKEND)
    print()
    print("=" * 58)
    print(f"  JARVIS Portable Edition v{VERSION}")
    print(f"  Interface : http://localhost:{JARVIS_PORT}")
    if info.get("openwebui"):
        print("  OpenWebUI : http://localhost:3000")
    print(f"  Backend   : {be.upper()} ({DEFAULT_MODEL})")
    print(f"  API       : http://localhost:{JARVIS_PORT}/api/jarvis")
    print(f"  Statut    : http://localhost:{JARVIS_PORT}/api/status")
    print("=" * 58)
    print("  Ctrl+C pour tout arreter")
    print()


def parse_args():
    parser = argparse.ArgumentParser(description="JARVIS Portable Edition")
    parser.add_argument("--diag", action="store_true",
                        help="Afficher le diagnostic systeme et quitter")
    return parser.parse_args()


def _start_ollama_backend(pm) -> str:
    # Portable force : on ignore volontairement tout serveur Ollama systeme
    # deja present sur OLLAMA_SYSTEM_PORT, meme s'il repond. Le backend utilise
    # par ollama_adapter.py est fige sur OLLAMA_PORT (portable), donc le
    # court-circuit systeme n'apportait rien d'autre qu'un risque de servir
    # un serveur avec de mauvais modeles/config.
    log("Ollama", "Demarrage force du binaire portable...")
    ollama_bin = ensure_ollama_binary(log)
    if ollama_bin:
        pm.start_ollama()
        time.sleep(OLLAMA_WAIT)
        if wait_for(f"http://localhost:{OLLAMA_PORT}/api/tags", "Ollama", log, timeout=OLLAMA_TIMEOUT):
            return DEFAULT_BACKEND
        log("Ollama", "Echec demarrage", False)
        return "echec"
    log("Ollama", "Installation impossible", False)
    return "absent"


def _start_core_services(pm, python) -> dict:
    log("JARVIS", "Demarrage du core API...")
    pm.start_jarvis(python)
    time.sleep(CORE_WAIT)
    pm.start_openwebui(python)
    jarvis_ok = wait_for(f"http://localhost:{JARVIS_PORT}/api/status", "JARVIS Core", log)
    owui_ok = pm.has_service("OpenWebUI") and wait_for("http://localhost:3000", "OpenWebUI", log)
    return {"jarvis": jarvis_ok, "openwebui": owui_ok}


def _run_diag():
    from services.diagnostic import DiagnosticService
    d = DiagnosticService()
    d.run_full()
    d.print_report()


def _shutdown(pm, signum, frame):
    """Arret propre sur SIGINT/SIGTERM : stop_all puis sortie via sys.exit.

    `sys.exit` declenche la fin normale de l'interpreteur (flush des buffers,
    handlers atexit, shutdown propre de uvicorn) — contrairement a `os._exit`
    qui court-circuite tout. Le `finally` garantit la sortie meme si stop_all
    leve.
    """
    print("  A bientot.")
    try:
        pm.stop_all()
    finally:
        sys.exit(0)


def main():
    os.chdir(BASE_DIR)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    # .env deja charge a l'import (voir haut du module) avant config.constants.
    pm = ProcessManager()

    signal.signal(signal.SIGINT, lambda s, f: _shutdown(pm, s, f))
    if hasattr(signal, "SIGTERM"):
        with contextlib.suppress(ValueError):
            signal.signal(signal.SIGTERM, lambda s, f: _shutdown(pm, s, f))

    _get_log_svc().log("INFO", "=== JARVIS demarrage ===")
    print(f"\n  JARVIS Portable Edition v{VERSION}")
    print(f"  OS : {SYSTEM}")
    print(f"  Python : {sys.version.split()[0]}")
    print(f"  Repertoire : {BASE_DIR}\n")

    python = ensure_venv(log)
    log("Init", f"Python : {python}")

    backend = _start_ollama_backend(pm)
    svc_info = _start_core_services(pm, python)

    info = {"backend": backend, **svc_info}
    print_banner(info)
    with contextlib.suppress(Exception):
        webbrowser.open(f"http://localhost:{JARVIS_PORT}")
    pm.monitor()


if __name__ == "__main__":
    args = parse_args()
    if args.diag:
        _run_diag()
    else:
        main()
