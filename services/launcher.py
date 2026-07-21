"""Launcher — Gestion propre du cycle de vie du processus Ollama.

Refacto DevOps / KISS :
- Responsabilité unique : gère UNIQUEMENT le binaire Ollama (plus Uvicorn/OpenWebUI).
- Suppression des hacks GPU (OLLAMA_VULKAN=0, CUDA_VISIBLE_DEVICES="").
- Health-check avec backoff exponentiel (remplace les time.sleep arbitraires).
- Injection de dépendances pour la testabilité (TDD).
"""
import logging
import os
import socket
import subprocess
import time
from typing import Callable, Optional

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


def wait_for_port_free(host: str, port: int, max_attempts: int = 10) -> bool:
    """Attend que le port soit libéré (évite les race conditions TIME_WAIT)."""
    for attempt in range(max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex((host, port)) != 0:
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    _logger.warning("Port %d toujours occupé après %d tentatives", port, max_attempts)
    return False


def wait_for_ollama_ready(host: str, port: int, timeout: float = DEFAULT_POLL_TIMEOUT) -> bool:
    """Health-check Ollama avec backoff exponentiel (pas de sleep fixe)."""
    url = f"http://{host}:{port}/api/tags"
    start_time = time.time()
    delay = 0.5

    while time.time() - start_time < timeout:
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0) # Backoff exponentiel plafonné à 5s
            
    return False


def _open_log(name: str):
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
    ):
        self._ollama_port = ollama_port
        self._base_dir = base_dir
        self._system = system
        self._max_restarts = max_restarts
        
        self._procs: list[tuple[subprocess.Popen, str]] = []
        self._restart_counts: dict[str, int] = {}
        self._shutting_down = False

    def start_ollama(self) -> Optional[subprocess.Popen]:
        """Démarre le serveur Ollama avec une configuration propre."""
        ollama_bin = get_ollama_path()
        if not ollama_bin:
            _logger.error("Binaire Ollama introuvable. Arrêt.")
            return None

        if not os.path.exists(ollama_bin):
            _logger.error("Chemin Ollama invalide : %s", ollama_bin)
            return None

        # Permissions Unix (exFAT/FAT32)
        if self._system != "windows":
            os.chmod(ollama_bin, 0o755)

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
                    stderr=subprocess.STDOUT, # Merge stderr into stdout
                )
            
            self._procs.append((p, "Ollama"))
            
            # Health-check robuste au lieu de time.sleep(3)
            if wait_for_ollama_ready("127.0.0.1", self._ollama_port):
                _logger.info("Ollama démarré avec succès sur le port %d", self._ollama_port)
                return p
            else:
                _logger.error("Ollama n'a pas répondu au health-check dans le temps imparti.")
                self._terminate_process(p, "Ollama")
                return None
                
        except Exception as e:
            _logger.exception("Échec critique au démarrage d'Ollama : %s", e)
            return None

    def stop_all(self):
        """Arrêt gracieux de tous les processus gérés."""
        self._shutting_down = True
        for p, name in reversed(self._procs):
            self._terminate_process(p, name)
        self._procs.clear()

    def _terminate_process(self, p: subprocess.Popen, name: str):
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
            time.sleep(2) # Polling interval pour le monitor
            
            dead_procs = [(p, name) for p, name in self._procs if p.poll() is not None]
            
            for p, name in dead_procs:
                self._procs.remove((p, name))
                self._restart_counts[name] = self._restart_counts.get(name, 0) + 1

                if self._restart_counts[name] > self._max_restarts:
                    _logger.critical("Processus %s crashé %d fois. Abandon.", name, self._max_restarts)
                    return False

                _logger.warning("Relance du processus %s (tentative %d/%d)...", 
                                name, self._restart_counts[name], self._max_restarts)
                time.sleep(1)
                if name == "Ollama":
                    self.start_ollama()

            if not self._procs and not self._shutting_down:
                # Si Ollama meurt et ne peut pas redémarrer
                return False

        return True
