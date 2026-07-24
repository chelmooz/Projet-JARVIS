"""Launcher — Gestion propre du cycle de vie du processus Ollama.

Refacto DevOps / KISS :
- Responsabilité unique : gère UNIQUEMENT le binaire Ollama (plus Uvicorn/OpenWebUI).
- Suppression des hacks GPU (OLLAMA_VULKAN=0, CUDA_VISIBLE_DEVICES="").
- Health-check avec backoff exponentiel (remplace les time.sleep arbitraires).
- Injection de dépendances pour la testabilité (TDD).
"""
from __future__ import annotations

import io
import logging
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

from config.paths import OLLAMA_HOST, OLLAMA_PORT
from services.port_manager import kill_existing
from services.system import BASE_DIR, SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.launcher")

MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Configuration par défaut (injectable pour les tests)
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_POLL_TIMEOUT = 60.0
DEFAULT_MAX_RESTARTS = 3

SOCKET_TIMEOUT = 0.5
INITIAL_BACKOFF = 0.5
BACKOFF_FACTOR = 1.5
MAX_BACKOFF = 5.0
POST_START_WAIT = 0.3
MONITOR_POLL_INTERVAL = 2.0
RESTART_DELAY = 1.0
PORT_POLL_WAIT = 0.5
PORT_POLL_MAX_ATTEMPTS = 10
HEALTH_CHECK_TIMEOUT = 2.0


def wait_for_port_free(host: str, port: int, max_attempts: int = PORT_POLL_MAX_ATTEMPTS) -> bool:
    """Attend que le port soit libéré (évite les race conditions TIME_WAIT)."""
    for _ in range(max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(SOCKET_TIMEOUT)
                if s.connect_ex((host, port)) != 0:
                    return True
        except OSError:
            pass
        time.sleep(PORT_POLL_WAIT)
    _logger.warning("Port %d toujours occupé après %d tentatives", port, max_attempts)
    return False


def wait_for_ollama_ready(host: str, port: int, timeout: float = DEFAULT_POLL_TIMEOUT) -> bool:
    """Health-check Ollama avec backoff exponentiel (pas de sleep fixe)."""
    url = f"http://{host}:{port}/api/tags"
    start_time = time.time()
    delay = INITIAL_BACKOFF

    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen(url, timeout=HEALTH_CHECK_TIMEOUT)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(delay)
            delay = min(delay * BACKOFF_FACTOR, MAX_BACKOFF)
            
    return False


def _open_log(name: str) -> io.TextIOWrapper:
    """Ouvre un fichier de log en mode append."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    path = os.path.join(LOGS_DIR, f"{name.lower().replace(' ', '_')}.log")
    return open(path, "a", encoding="utf-8")


class ProcessManager:
    """Gère le cycle de vie du processus Ollama (SPOF critique).
    
    KISS : Ne gère plus Uvicorn ni OpenWebUI. 
    Uvicorn doit être lancé directement par le processus principal (jarvis.py).
    """

    def __init__(
        self,
        ollama_port: int = OLLAMA_PORT,
        base_dir: str = BASE_DIR,
        system: str = SYSTEM,
        max_restarts: int = DEFAULT_MAX_RESTARTS,
    ) -> None:
        self._ollama_port = ollama_port
        self._base_dir = base_dir
        self._system = system
        self._max_restarts = max_restarts
        
        self._procs: list[tuple[subprocess.Popen[bytes], str]] = []
        self._restart_counts: dict[str, int] = {}
        self._shutting_down = False

    def start_ollama(self) -> subprocess.Popen[bytes] | None:
        """Démarre le serveur Ollama avec une configuration propre."""
        ollama_bin = get_ollama_path()
        if not ollama_bin:
            _logger.error("Binaire Ollama introuvable. Arrêt.")
            return None

        # Permissions Unix (exFAT/FAT32)
        if self._system != "windows":
            try:
                os.chmod(ollama_bin, 0o755)
            except OSError as e:
                _logger.warning("Impossible de fixer les permissions sur %s : %s", ollama_bin, e)

        kill_existing("ollama", self._ollama_port)
        wait_for_port_free("127.0.0.1", self._ollama_port)
        os.makedirs(os.path.join(MODELS_DIR, "ollama"), exist_ok=True)

        env = os.environ.copy()
        env["OLLAMA_HOST"] = OLLAMA_HOST
        env["OLLAMA_MODELS"] = os.path.join(MODELS_DIR, "ollama")
        env["OLLAMA_KEEP_ALIVE"] = "5m"
        # NOTE : On ne force PLUS OLLAMA_VULKAN=0 ni CUDA_VISIBLE_DEVICES="" 
        # pour laisser Ollama utiliser le GPU si disponible.

        try:
            with _open_log("ollama") as log_file:
                p = subprocess.Popen(
                    [ollama_bin, "serve"],
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                )
            
            self._procs.append((p, "Ollama"))

            # Détection rapide d'un échec immédiat (binaire corrompu, crash au
            # lancement) : on ne bloque plus sur un health-check HTTP complet
            # ici (wait_for_ollama_ready reste disponible pour un appelant qui
            # veut attendre la disponibilité réelle de l'API Ollama).
            time.sleep(POST_START_WAIT)
            if p.poll() is not None:
                _logger.error(
                    "Ollama s'est arrêté immédiatement après le lancement (code %s).",
                    p.poll(),
                )
                return None

            _logger.info("Ollama démarré avec succès sur le port %d", self._ollama_port)
            return p

        except Exception as e:
            _logger.exception("Échec critique au démarrage d'Ollama : %s", e)
            return None

    def stop_all(self) -> None:
        """Arrêt gracieux de tous les processus gérés."""
        self._shutting_down = True
        for p, name in reversed(self._procs):
            self._terminate_process(p, name)
        self._procs.clear()

    def _terminate_process(self, p: subprocess.Popen[bytes], name: str) -> None:
        """Arrête un processus proprement (SIGTERM puis SIGKILL)."""
        try:
            p.terminate()
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _logger.warning("Arrêt forcé (SIGKILL) du processus %s", name)
            p.kill()
        except Exception as e:
            _logger.warning("Erreur lors de l'arrêt de %s : %s", name, e)

    def monitor(self) -> bool:
        """Boucle de surveillance minimaliste avec relance limitée."""
        while not self._shutting_down:
            time.sleep(MONITOR_POLL_INTERVAL)
            
            dead_procs = [(p, name) for p, name in self._procs if p.poll() is not None]
            
            for p, name in dead_procs:
                self._procs.remove((p, name))
                self._restart_counts[name] = self._restart_counts.get(name, 0) + 1

                if self._restart_counts[name] > self._max_restarts:
                    _logger.critical("Processus %s crashé %d fois. Abandon.", name, self._max_restarts)
                    return False

                _logger.warning("Relance du processus %s (tentative %d/%d)...", 
                                name, self._restart_counts[name], self._max_restarts)
                time.sleep(RESTART_DELAY)
                if name == "Ollama":
                    self.start_ollama()

            if not self._procs and not self._shutting_down:
                # Si Ollama meurt et ne peut pas redémarrer
                return False

        return True


__all__ = [
    "ProcessManager",
    "wait_for_port_free",
    "wait_for_ollama_ready",
]
