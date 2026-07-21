"""Launcher — Démarrage/arrêt des processus (Ollama, JARVIS, OpenWebUI).

⚠️ NOTE DEVOPS : Ce module est un composant "Portable/Legacy".
Dans l'architecture cible (Docker), la gestion du cycle de vie des processus
est déléguée à l'orchestrateur de conteneurs. Ce fichier ne doit contenir
aucune logique d'installation système ou de téléchargement.
"""
import contextlib
import logging
import os
import socket
import subprocess
import time
import urllib.request
from typing import Callable, Optional

from config.constants import (
    JARVIS_PORT,
    LAUNCHER_MONITOR_SLEEP,
    LAUNCHER_PIP_TIMEOUT,
    LAUNCHER_POLL_SLEEP,
    LAUNCHER_PORT_POLL_MAX,
    LAUNCHER_PORT_POLL_SLEEP,
    LAUNCHER_PROCESS_WAIT,
    LAUNCHER_RESTART_DELAY,
    LAUNCHER_START_DELAY,
    LAUNCHER_URLOPEN_TIMEOUT,
    LAUNCHER_WAIT_TIMEOUT,
)
from config.paths import OLLAMA_HOST, OLLAMA_PORT
from services.port_manager import kill_existing
from services.system import BASE_DIR, SYSTEM, get_ollama_path, find_python

_logger = logging.getLogger("jarvis.launcher")

MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# TODO: Déplacer dans config.constants pour centralisation
MAX_RESTART = 2


def wait_for_port_free(host: str, port: int, log: Callable = _logger.info) -> bool:
    """Attend que le port soit libéré après un kill (évite les race conditions TIME_WAIT)."""
    for attempt in range(LAUNCHER_PORT_POLL_MAX):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(LAUNCHER_PORT_POLL_SLEEP)
                if s.connect_ex((host, port)) != 0:
                    log(f"Port {port} libéré après {attempt + 1} tentative(s)")
                    return True
        except OSError:
            pass
        time.sleep(LAUNCHER_PORT_POLL_SLEEP)
    log(f"Port {port} toujours occupé après {LAUNCHER_PORT_POLL_MAX} tentatives")
    return False


def wait_for(url: str, label: str, log: Callable, timeout: int = LAUNCHER_WAIT_TIMEOUT) -> bool:
    """Attend qu'une URL réponde (polling 1s)."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=LAUNCHER_URLOPEN_TIMEOUT)
            log(label, f"Prêt sur {url}")
            return True
        except Exception as e:
            _logger.debug("Attente URL %s: %s", url, e)
            time.sleep(LAUNCHER_POLL_SLEEP)
    log(label, f"Indisponible après {timeout}s", False)
    return False


def _open_log(name: str):
    """Ouvre un fichier de log en mode append dans logs/."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    path = os.path.join(LOGS_DIR, name.lower().replace(" ", "_") + ".log")
    return open(path, "a", encoding="utf-8")


def _resolve_ollama_binary() -> Optional[str]:
    """Résout le chemin du binaire Ollama et applique les permissions nécessaires."""
    ollama = get_ollama_path()
    if not ollama:
        return None
    # Correction des permissions pour les clés USB exFAT/FAT32 (Unix)
    if SYSTEM != "windows" and os.path.exists(ollama):
        with contextlib.suppress(OSError):
            os.chmod(ollama, 0o755)
    return ollama


def _build_ollama_env() -> dict:
    """Construit l'environnement d'exécution pour Ollama (isole les hacks OS)."""
    env = os.environ.copy()
    env["OLLAMA_HOST"] = OLLAMA_HOST
    env["OLLAMA_MODELS"] = os.path.join(MODELS_DIR, "ollama")
    env["OLLAMA_KEEP_ALIVE"] = "5m"

    if SYSTEM != "windows":
        lib_dir = os.path.join(BASE_DIR, "lib", "ollama")
        if os.path.exists(lib_dir):
            env["OLLAMA_LIBRARY_PATH"] = lib_dir

    # Désactivation GPU forcée en mode portable pour éviter les crashes
    if SYSTEM in ("linux", "windows"):
        env["OLLAMA_VULKAN"] = "0"
    if SYSTEM == "windows":
        env["CUDA_VISIBLE_DEVICES"] = ""

    return env


class ProcessManager:
    """Gère le cycle de vie des processus fils (démarrage, arrêt, surveillance).
    
    Responsabilité unique : Superviser les processus.
    Ne gère ni l'installation, ni la configuration système profonde.
    """

    def __init__(self):
        self.procs: list[tuple[subprocess.Popen, str]] = []
        self.restart_counts: dict[str, int] = {}
        self._shutting_down = False
        self._critical = {"Ollama", "JARVIS Core"}

    def start_ollama(self) -> Optional[subprocess.Popen]:
        """Démarre le serveur Ollama."""
        ollama_bin = _resolve_ollama_binary()
        if not ollama_bin:
            _logger.warning("Binaire Ollama introuvable")
            return None

        kill_existing("ollama", OLLAMA_PORT)
        wait_for_port_free("127.0.0.1", OLLAMA_PORT)
        os.makedirs(os.path.join(MODELS_DIR, "ollama"), exist_ok=True)

        try:
            with _open_log("ollama") as log_file:
                p = subprocess.Popen(
                    [ollama_bin, "serve"],
                    env=_build_ollama_env(),
                    stdout=log_file,
                    stderr=log_file
                )
            time.sleep(LAUNCHER_START_DELAY)
            if p.poll() is not None:
                _logger.error("Ollama a crashé au démarrage")
                return None
            self.procs.append((p, "Ollama"))
            return p
        except Exception as e:
            _logger.exception("Échec démarrage Ollama: %s", e)
            return None

    def start_jarvis(self, python: str) -> Optional[subprocess.Popen]:
        """Démarre l'API FastAPI JARVIS."""
        controller_path = os.path.join(BASE_DIR, "controllers", "router.py")
        if not os.path.exists(controller_path):
            _logger.warning("Contrôleur JARVIS introuvable: %s", controller_path)
            return None

        kill_existing("jarvis", JARVIS_PORT)
        wait_for_port_free("127.0.0.1", JARVIS_PORT)

        cmd = [
            python, "-m", "uvicorn",
            "controllers.router:app",
            "--host", "127.0.0.1",
            "--port", str(JARVIS_PORT)
        ]
        try:
            with _open_log("jarvis_api") as log_file:
                p = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=log_file)
            self.procs.append((p, "JARVIS Core"))
            return p
        except Exception as e:
            _logger.exception("Échec démarrage JARVIS API: %s", e)
            return None

    def start_openwebui(self, python: str) -> Optional[subprocess.Popen]:
        """Démarre OpenWebUI si activé et installé."""
        if os.environ.get("JARVIS_ENABLE_OPENWEBUI", "0").lower() != "1":
            return None

        try:
            r = subprocess.run(
                [python, "-m", "pip", "show", "open-webui"],
                capture_output=True, text=True, timeout=LAUNCHER_PIP_TIMEOUT
            )
            if r.returncode != 0:
                return None
        except Exception as e:
            _logger.warning("OpenWebUI non installé ou pip échoue: %s", e)
            return None

        try:
            with _open_log("openwebui") as log_file:
                p = subprocess.Popen(
                    [python, "-m", "open_webui", "serve", "--port", "3000"],
                    stdout=log_file, stderr=log_file
                )
            self.procs.append((p, "OpenWebUI"))
            return p
        except Exception as e:
            _logger.exception("Échec démarrage OpenWebUI: %s", e)
            return None

    def has_service(self, name: str) -> bool:
        return any(n == name for _, n in self.procs)

    def _stop_one(self, name: str):
        for p, n in reversed(self.procs):
            if n == name:
                self._terminate_process(p, name)
                self.procs.remove((p, name))
                break

    def stop_all(self):
        self._shutting_down = True
        for p, name in reversed(self.procs):
            self._terminate_process(p, name)
        self.procs.clear()

    def _terminate_process(self, p: subprocess.Popen, name: str):
        try:
            p.terminate()
            p.wait(timeout=LAUNCHER_PROCESS_WAIT)
        except Exception as e:
            _logger.warning("Arrêt processus %s: %s", name, e)
            with contextlib.suppress(Exception):
                p.kill()

    def monitor(self) -> bool:
        """Boucle de surveillance avec relance automatique (limitée)."""
        while True:
            time.sleep(LAUNCHER_MONITOR_SLEEP)
            if self._shutting_down:
                return True

            dead = [(p, name) for p, name in self.procs if p.poll() is not None]
            for p, name in dead:
                self.procs.remove((p, name))
                key = name.lower().replace(" ", "_")
                self.restart_counts[key] = self.restart_counts.get(key, 0) + 1

                if self.restart_counts[key] > MAX_RESTART and name in self._critical:
                    _logger.error("Abandon %s: trop de crashs (%d)", name, MAX_RESTART)
                    self.stop_all()
                    return False

                if self.restart_counts[key] <= MAX_RESTART:
                    time.sleep(LAUNCHER_RESTART_DELAY)
                    self._restart(name)

            if not self.procs:
                return True

    def _restart(self, name: str):
        restart_map = {
            "Ollama": self.start_ollama,
            "JARVIS Core": lambda: self.start_jarvis(find_python()),
            "OpenWebUI": lambda: self.start_openwebui(find_python()),
        }
        fn = restart_map.get(name)
        if fn:
            try:
                fn()
            except Exception as e:
                _logger.exception("Échec relance %s: %s", name, e)
