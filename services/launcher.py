"""Launcher — Démarrage/arrêt des processus (Ollama, JARVIS, OpenWebUI).

Cycle de vie complet :
  - start_ollama, start_jarvis, start_openwebui
  - stop_all (arrêt propre ou kill forcé)
  - monitor (boucle de surveillance avec relance automatique)

Installation du binaire Ollama déléguée à services/ollama_installer.py.
"""
import contextlib
import logging
import os
import socket
import subprocess
import time
import urllib.request

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
from services.system import BASE_DIR, SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.launcher")

MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

MAX_RESTART = 2


def wait_for_port_free(host: str, port: int, log) -> bool:
    """Attend que le port soit libéré après un kill.

    Remplace time.sleep(LAUNCHER_KILL_DELAY) pour eviter la race condition
    sur les sockets en TIME_WAIT. Utilise une boucle active avec backoff.

    Args:
        host: Adresse de l'hote (ex: "127.0.0.1")
        port: Numero de port a verifier
        log: Fonction de log (ex: _logger.info ou print)

    Returns:
        True si le port est libre, False si timeout.
    """
    for attempt in range(LAUNCHER_PORT_POLL_MAX):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(LAUNCHER_PORT_POLL_SLEEP)
                result = s.connect_ex((host, port))
                if result != 0:
                    log(f"Port {port} libere apres {attempt + 1} tentative(s)")
                    return True
        except Exception:
            pass
        time.sleep(LAUNCHER_PORT_POLL_SLEEP)
    log(f"Port {port} toujours occupe apres {LAUNCHER_PORT_POLL_MAX} tentatives")
    return False


def _open_log(name):
    """Ouvre un fichier de log en mode append dans logs/ (UTF-8 pour les accents)."""
    path = os.path.join(LOGS_DIR, name.lower().replace(" ", "_") + ".log")
    return open(path, "a", encoding="utf-8")


class ProcessManager:
    """Gère le cycle de vie des processus fils (démarrage, arrêt, surveillance)."""

    def __init__(self):
        self.procs: list[tuple[subprocess.Popen, str]] = []
        self.restart_counts: dict[str, int] = {}
        self._shutting_down = False
        self._critical = {"Ollama", "JARVIS Core"}

    def start_ollama(self) -> subprocess.Popen | None:
        """Démarre le serveur Ollama (LLM, port 11436)."""
        ollama = get_ollama_path()
        if not ollama:
            return None
        kill_existing("ollama", OLLAMA_PORT)
        # Attendre que le port soit reellement libere (TIME_WAIT) avant de
        # lancer le nouveau processus. Contourne la race condition où le
        # socket met du temps a se liberer apres kill_existing().
        wait_for_port_free("127.0.0.1", OLLAMA_PORT, _logger.info)
        os.makedirs(os.path.join(MODELS_DIR, "ollama"), exist_ok=True)
        env = os.environ.copy()
        env["OLLAMA_HOST"] = OLLAMA_HOST
        env["OLLAMA_MODELS"] = os.path.join(MODELS_DIR, "ollama")
        env["OLLAMA_KEEP_ALIVE"] = "5m"
        if SYSTEM != "windows":
            lib_dir = os.path.join(BASE_DIR, "lib", "ollama")
            if os.path.exists(lib_dir):
                env["OLLAMA_LIBRARY_PATH"] = lib_dir
        if SYSTEM in ("linux", "windows"):
            env["OLLAMA_VULKAN"] = "0"
        if SYSTEM == "windows":
            env["CUDA_VISIBLE_DEVICES"] = ""
        if SYSTEM != "windows" and os.path.exists(ollama):
            # Cle USB exFAT/FAT32 ne conserve pas le bit d'execution Unix.
            os.chmod(ollama, 0o755)
        try:
            with _open_log("ollama") as f_err:
                p = subprocess.Popen([ollama, "serve"], env=env, stdout=f_err, stderr=f_err)
            time.sleep(LAUNCHER_START_DELAY)
            if p.poll() is not None:
                return None
            self.procs.append((p, "Ollama"))
            return p
        except Exception as e:
            _logger.warning("Echec demarrage Ollama: %s", e)
            return None

    def start_jarvis(self, python: str) -> subprocess.Popen | None:
        """Démarre l'API FastAPI JARVIS (uvicorn, port 8000)."""
        controller_path = os.path.join(BASE_DIR, "controllers", "router.py")
        if not os.path.exists(controller_path):
            return None
        # Libere le port 8000 si une instance fantome (crash precedent, double
        # lancement) le retient encore. Sans ca, uvicorn crash en Errno 10048
        # et le launcher finit par abandonner -> stop_all() tue Ollama.
        kill_existing("jarvis", JARVIS_PORT)
        # Attendre que le port 8000 soit libere avant de lancer uvicorn.
        wait_for_port_free("127.0.0.1", JARVIS_PORT, _logger.info)
        cmd = [python, "-m", "uvicorn", "controllers.router:app", "--host", "127.0.0.1", "--port", str(JARVIS_PORT)]
        try:
            with _open_log("jarvis_api") as f_err:
                p = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=f_err, stderr=f_err)
            self.procs.append((p, "JARVIS Core"))
            return p
        except Exception as e:
            _logger.warning("Echec demarrage JARVIS API: %s", e)
            return None

    def start_openwebui(self, python: str) -> subprocess.Popen | None:
        """Démarre OpenWebUI si installé (interface web, port 3000).

        Opt-in explicite via JARVIS_ENABLE_OPENWEBUI=1 : un outil de diagnostic
        doit rester minimaliste par defaut et ne pas alourdir la memoire si
        OpenWebUI est present mais non souhaite.
        """
        if os.environ.get("JARVIS_ENABLE_OPENWEBUI", "0").lower() != "1":
            return None
        try:
            r = subprocess.run([python, "-m", "pip", "show", "open-webui"], capture_output=True, text=True, timeout=LAUNCHER_PIP_TIMEOUT)
            if r.returncode != 0:
                return None
        except Exception as e:
            _logger.warning("OpenWebUI non installe ou pip echoue: %s", e)
            return None
        try:
            with _open_log("openwebui") as f_err:
                p = subprocess.Popen([python, "-m", "open_webui", "serve", "--port", "3000"],
                                     stdout=f_err, stderr=f_err)
            self.procs.append((p, "OpenWebUI"))
            return p
        except Exception as e:
            _logger.warning("Echec demarrage OpenWebUI: %s", e)
            return None

    def has_service(self, name: str) -> bool:
        """Vérifie si un service est en cours d'exécution par son nom."""
        return any(n == name for _, n in self.procs)

    def _stop_one(self, name: str):
        """Arrête proprement (ou tue) un seul service nommé."""
        for p, n in reversed(self.procs):
            if n == name:
                try:
                    p.terminate()
                    p.wait(timeout=LAUNCHER_PROCESS_WAIT)
                except Exception as e:
                    _logger.warning("Arret processus %s: %s", name, e)
                    with contextlib.suppress(Exception):
                        p.kill()
                self.procs.remove((p, name))
                break

    def stop_all(self):
        self._shutting_down = True
        for p, name in reversed(self.procs):
            try:
                p.terminate()
                p.wait(timeout=LAUNCHER_PROCESS_WAIT)
            except Exception as e:
                _logger.warning("Arret processus %s: %s", name, e)
                with contextlib.suppress(Exception):
                    p.kill()
        self.procs.clear()

    def monitor(self) -> bool:
        while True:
            time.sleep(LAUNCHER_MONITOR_SLEEP)
            if self._shutting_down:
                return True
            dead = [(p, name) for p, name in self.procs if p.poll() is not None]
            for p, name in dead:
                self.procs.remove((p, name))
                key = name.lower().replace(" ", "_")
                self.restart_counts.setdefault(key, 0)
                self.restart_counts[key] += 1
                if self.restart_counts[key] > MAX_RESTART and name in self._critical:
                    _logger.error("Abandon %s: trop de crashs (%d)", name, MAX_RESTART)
                    # Stop propre de tous les services pour ne laisser aucun
                    # processus orphelin : sinon Ollama reste accroche le port
                    # 11436 au relaunch suivant et fausse le diagnostic. La main
                    # est rendue apres nettoyage.
                    self.stop_all()
                    return False
                if self.restart_counts[key] <= MAX_RESTART:
                    time.sleep(LAUNCHER_RESTART_DELAY)
                    try:
                        self._restart(name)
                    except Exception as e:
                        _logger.exception("Echec relance %s: %s", name, e)
            if not self.procs:
                return True

    def _restart(self, name: str):
        """Relance un processus par son nom."""
        from services.system import find_python
        restart_map = {
            "Ollama": lambda: self.start_ollama(),
            "JARVIS Core": lambda: self.start_jarvis(find_python()),
            "OpenWebUI": lambda: self.start_openwebui(find_python()),
        }
        fn = restart_map.get(name)
        if fn:
            fn()

def wait_for(url: str, label: str, log, timeout: int = LAUNCHER_WAIT_TIMEOUT) -> bool:
    """Attend qu'une URL réponde (timeout en secondes), avec polling 1s."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=LAUNCHER_URLOPEN_TIMEOUT)
            log(label, f"Pret sur {url}")
            return True
        except Exception as e:
            _logger.debug("Attente URL %s: %s", url, e)
            time.sleep(LAUNCHER_POLL_SLEEP)
    log(label, f"Indisponible apres {timeout}s", False)
    return False
