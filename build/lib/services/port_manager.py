"""Port Manager — Gestion des ports et nettoyage des processus résiduels."""
import logging
import os
import re
import subprocess

from services.system import SYSTEM

KILL_TIMEOUT = 5
WAIT_TIMEOUT = 3


_LOCAL_ADDR_RE = re.compile(r"[\w.\[\]:]+:(\d+)")


def _extract_port(address: str) -> int | None:
    """Extrait le port EXACT d'une adresse locale (ex. '0.0.0.0:8000' -> 8000).

    Match précis (premier 'adresse:port' de la ligne = adresse locale pour
    netstat/ss) : un port '80' ne doit PAS matcher '8000'/'18080'. Renvoie
    None si aucun port trouvé.
    """
    m = _LOCAL_ADDR_RE.search(address)
    if not m:
        return None
    return int(m.group(1))


def _kill_windows(port: int) -> None:
    r = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=KILL_TIMEOUT)
    stdout = r.stdout.decode("utf-8", errors="replace")
    for line in stdout.splitlines():
        if _extract_port(line) != port or "LISTENING" not in line:
            continue
        parts = line.strip().split()
        if parts and parts[-1].isdigit():
            pid = int(parts[-1])
            if pid != 0 and pid != os.getpid():
                # /t = termine aussi l'arbre de processus enfants (ex. model runners
                # Ollama résiduels) pour libérer le port après un retrait brutal de clef USB.
                subprocess.run(["taskkill", "/f", "/t", "/pid", str(pid)], capture_output=True, timeout=WAIT_TIMEOUT)


def _kill_linux(port: int) -> None:
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=KILL_TIMEOUT)
    except FileNotFoundError:
        _kill_linux_fallback(port)


def _kill_linux_fallback(port: int) -> None:
    """Fallback si `fuser` absent (Debian minimal, Alpine) : `ss` puis `kill`."""
    try:
        r = subprocess.run(
            ["ss", "-ltnp", f"sport = :{port}"],
            capture_output=True, text=True, timeout=KILL_TIMEOUT,
        )
    except FileNotFoundError:
        return
    for line in r.stdout.splitlines():
        if _extract_port(line) != port:
            continue
        m = re.search(r"pid=(\d+)", line)
        if m:
            pid = int(m.group(1))
            if pid and pid != os.getpid():
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, timeout=KILL_TIMEOUT)


def _kill_darwin(port: int) -> None:
    r = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=KILL_TIMEOUT)
    if r.stdout.strip():
        for pid in r.stdout.strip().splitlines():
            if pid and int(pid) != os.getpid():
                subprocess.run(["kill", "-9", pid.strip()], capture_output=True, timeout=WAIT_TIMEOUT)


def kill_existing(process_name: str, port: int) -> None:
    """Tue les processus résiduels sur un port donné au démarrage."""
    logging.debug("kill_existing: tentative kill %s sur le port %s", process_name, port)
    try:
        {"windows": _kill_windows, "linux": _kill_linux, "darwin": _kill_darwin}[SYSTEM](port)
    except Exception as exc:
        logging.debug("kill_existing: echec kill %s sur le port %s: %s", process_name, port, exc)
