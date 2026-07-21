"""Checks — 8 fonctions pures de diagnostic machine.
Chaque fonction retourne un dict. Aucun état partagé."""
import logging
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import urllib.request

import psutil

from config.constants import PROJECT_DIR
from services.diagnostics.rules import PORTS
from services.system import PORTABLE_DIR, VENV_DIR, find_python, get_ollama_path

GPU_TIMEOUT = 5
NETWORK_TIMEOUT = 1
INTERNET_TIMEOUT = 3

_logger = logging.getLogger("jarvis.diagnostic.checks")


def _apple_cpu_brand() -> str:
    try:
        r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:
        _logger.debug("sysctl cpu brand_string : %s", e)
    return ""


def check_os() -> dict:
    uname = platform.uname()
    dist = platform.platform()
    if hasattr(platform, "freedesktop_os_release"):
        try:
            release = platform.freedesktop_os_release()
            dist = " ".join(release.get(x, "?") for x in ["ID", "VERSION_ID"])
        except OSError:
            pass
    return {
        "os": platform.system().lower(),
        "dist": dist,
        "arch": uname.machine,
        "hostname": uname.node,
        "kernel": uname.release,
    }


def check_cpu() -> dict:
    model = "?"
    arch = platform.machine()
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":")[1].strip()
                    break
    except Exception as e:
        _logger.debug("Impossible de lire /proc/cpuinfo : %s", e)
    if not model or model == "?":
        apple = _apple_cpu_brand()
        if apple:
            model = apple
    is_apple_silicon = (sys.platform == "darwin" and arch == "arm64")
    return {
        "model": model,
        "arch": arch,
        "apple_silicon": is_apple_silicon,
        "cores_logical": os.cpu_count() or 0,
        "cores_physical": psutil.cpu_count(logical=False) or 0,
        "load_percent": psutil.cpu_percent(interval=0.1),
        "arch_bits": struct.calcsize("P") * 8,
    }


def check_ram() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024 ** 3), 1),
        "available_gb": round(mem.available / (1024 ** 3), 1),
        "used_percent": mem.percent,
        "swap_gb": round(psutil.swap_memory().total / (1024 ** 3), 1),
    }


def warn_low_memory(threshold_gb: float = 2.0) -> dict | None:
    """Avertit (logging) si la RAM disponible est sous le seuil.

    psutil est déjà une dépendance du projet ; coût marginal. Retourne le
    dict d'avertissement ou None si la RAM est suffisante.
    """
    ram = check_ram()
    if ram["available_gb"] < threshold_gb:
        _logger.warning(
            "RAM disponible faible (%s Go < %s Go) — le chargement de modeles peut echouer",
            ram["available_gb"], threshold_gb,
        )
        return {"level": "warning", "available_gb": ram["available_gb"], "threshold_gb": threshold_gb}
    return None


def _detect_gpu(cmd, vendor, detail_fn):
    """Helper subprocess pour détection GPU (NVIDIA/AMD)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=GPU_TIMEOUT)
        if r.returncode == 0 and r.stdout.strip():
            return {"detected": True, "vendor": vendor, "detail": detail_fn(r.stdout.strip())}
    except Exception as e:
        _logger.debug("%s : %s", vendor, e)
    return None


def _parse_nvidia_vram(stdout: str) -> float:
    """Parse la VRAM depuis la sortie nvidia-smi (format: 'name, XXXX MiB')."""
    for line in stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(",", 1)
        if len(parts) == 2:
            vram_str = parts[1].strip().lower()
            try:
                if "mib" in vram_str:
                    return round(float(vram_str.replace("mib", "").strip()) / 1024, 1)
                if "gib" in vram_str:
                    return round(float(vram_str.replace("gib", "").strip()), 1)
            except (ValueError, TypeError):
                pass
    return 0.0


def check_gpu() -> dict:
    result = _detect_gpu(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        "nvidia",
        lambda s: [line.strip() for line in s.split("\n") if line.strip()][0],
    )
    if result:
        vram = 0.0
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=GPU_TIMEOUT,
            )
            if r.returncode == 0:
                vram = _parse_nvidia_vram(r.stdout)
        except Exception as e:
            _logger.debug("Lecture VRAM nvidia-smi echouee: %s", e)
        result["vram_gb"] = vram
        return result
    result = _detect_gpu(
        ["rocm-smi", "--showproductname"],
        "amd",
        lambda s: s[:120],
    )
    if result:
        result["vram_gb"] = 0.0
        return result
    if sys.platform == "darwin":
        apple = _apple_cpu_brand()
        if apple:
            return {"detected": True, "vendor": "apple", "detail": apple, "vram_gb": 0.0}
    return {"detected": False, "vendor": None, "detail": "Aucun GPU detecte", "vram_gb": 0.0}


def check_python() -> dict:
    in_venv = sys.prefix != sys.base_prefix
    venv_python = os.path.join(VENV_DIR, "bin", "python")
    if sys.platform == "win32":
        venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    venv_ok = os.path.exists(venv_python)
    selected_python = find_python()
    portable_ok = os.path.exists(selected_python) and os.path.abspath(selected_python).startswith(os.path.abspath(PORTABLE_DIR))
    required = ["fastapi", "uvicorn", "numpy", "psutil", "yaml", "httpx"]
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return {
        "version": sys.version.split()[0],
        "executable": sys.executable,
        "selected_python": selected_python,
        "in_venv": in_venv,
        "venv_ok": venv_ok,
        "portable_ok": portable_ok,
        "python_env_ok": venv_ok or portable_ok,
        "missing_deps": missing,
    }


def check_binaries() -> list[dict]:
    results = []
    for name, fn in [("ollama", get_ollama_path)]:
        path = fn()
        info = {"name": name, "path": path, "exists": path is not None}
        if path and os.path.exists(path):
            try:
                r = subprocess.run(["file", path], capture_output=True, text=True, timeout=5)
                info["file_info"] = r.stdout.strip()
            except Exception as e:
                _logger.debug("Commande 'file' echouee pour %s: %s", path, e)
                info["file_info"] = None
        results.append(info)
    return results


def check_network() -> dict:
    ports_status = {}
    for port in PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(NETWORK_TIMEOUT)
            ports_status[str(port)] = "in_use" if s.connect_ex(("127.0.0.1", port)) == 0 else "free"
    internet = False
    try:
        urllib.request.urlopen("http://1.1.1.1", timeout=INTERNET_TIMEOUT)
        internet = True
    except Exception as e:
        _logger.debug("internet check : %s", e)
    return {"internet": internet, "ports": ports_status}


def check_disk() -> dict:
    usage = shutil.disk_usage(PROJECT_DIR)
    mount = PROJECT_DIR
    while mount and not os.path.ismount(mount):
        parent = os.path.dirname(mount)
        if parent == mount:
            break
        mount = parent
    return {
        "project_dir": PROJECT_DIR,
        "mount_point": mount,
        "total_gb": round(usage.total / (1024 ** 3), 1),
        "free_gb": round(usage.free / (1024 ** 3), 1),
        "used_percent": round(usage.used / usage.total * 100, 1) if usage.total else 0,
    }
