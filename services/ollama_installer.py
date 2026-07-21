"""OllamaInstaller — Téléchargement, vérification et installation du binaire Ollama.

Extrait de services/launcher.py (refactor Q4).
Responsabilités :
  - Téléchargement atomique (_download_file)
  - Vérification SHA256 (_sha256_of, _expected_ollama_sha256, _verify_ollama_binary)
  - Installation plateforme (apt, tar, zip, brew, script)
  - Point d'entrée unique ensure_ollama_binary
"""
import contextlib
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile

from config.constants import (
    LAUNCHER_DOWNLOAD_TIMEOUT,
    LAUNCHER_INSTALL_TIMEOUT,
    LAUNCHER_WAIT_TIMEOUT,
    OLLAMA_VERSION,
)
from services.system import BASE_DIR, BIN_DIR, SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.ollama_installer")


def _download_file(url: str, dest: str, log, timeout: int = LAUNCHER_DOWNLOAD_TIMEOUT):
    os.makedirs(os.path.dirname(dest), exist_ok=True) if os.path.dirname(dest) else None
    part = f"{dest}.part"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as f:
            while True:
                block = resp.read(1 << 20)
                if not block:
                    break
                f.write(block)
        os.replace(part, dest)
    except Exception:
        if os.path.exists(part):
            with contextlib.suppress(OSError):
                os.remove(part)
        raise


def _sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _expected_ollama_sha256(asset_name: str, log) -> str | None:
    try:
        url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/sha256sums.txt"
        with urllib.request.urlopen(url, timeout=LAUNCHER_DOWNLOAD_TIMEOUT) as r:
            content = r.read().decode("utf-8", "ignore")
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].strip("*") == asset_name:
                return parts[0].lower()
    except Exception as e:
        _logger.debug("SHA256 Ollama indisponible (offline ?): %s", e)
        log("Ollama", "Verification SHA256 sautée (source de hash indisponible)", False)
    return None


def _verify_ollama_binary(path: str, asset_name: str, log) -> bool:
    expected = _expected_ollama_sha256(asset_name, log)
    if expected is None:
        return True
    actual = _sha256_of(path).lower()
    if actual != expected:
        log("Ollama", f"SHA256 MISMATCH: attendu {expected}, obtenu {actual}", False)
        return False
    log("Ollama", "Integrite SHA256 verifiee")
    return True


def _install_linux_apt(log) -> str | None:
    try:
        log("Ollama", "Tentative apt install ollama...")
        r = subprocess.run(["apt", "install", "-y", "ollama"], capture_output=True, text=True, timeout=LAUNCHER_INSTALL_TIMEOUT)
        if r.returncode == 0:
            return shutil.which("ollama")
    except Exception as e:
        log("Ollama", "apt introuvable ou echec", False)
        _logger.debug("Echec apt install ollama: %s", e)
    return None


def _extract_tar_zst(archive: str, dest_dir: str, log) -> None:
    """Extrait une archive .tar.zst.

    `tar --zstd` nécessite le binaire externe `zstd`, absent sur une Debian/
    Ubuntu minimale (clé USB bootable). Si l'option échoue faute de binaire,
    on retombe sur `tar -xf` : les `tar` récents (libarchive/liblzma) savent
    souvent auto-détecter zstd sans dépendance externe.
    """
    try:
        subprocess.run(["tar", "--zstd", "xf", archive, "-C", dest_dir], check=True, timeout=LAUNCHER_WAIT_TIMEOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log("Ollama", "tar --zstd indisponible (binaire zstd manquant ?), fallback tar -xf", False)
        _logger.debug("Echec tar --zstd: %s", e)
        subprocess.run(["tar", "-xf", archive, "-C", dest_dir], check=True, timeout=LAUNCHER_WAIT_TIMEOUT)


def _install_linux_tar(log) -> str | None:
    log("Ollama", "Telechargement binaire Linux...")
    arch = platform.machine()
    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    ollama_arch = arch_map.get(arch, "amd64")
    url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-linux-{ollama_arch}.tar.zst"
    cache_dir = os.path.join(BASE_DIR, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    dl = os.path.join(cache_dir, "ollama-linux.tar.zst")
    dl_bin = os.path.join(cache_dir, "ollama-extract")
    os.makedirs(dl_bin, exist_ok=True)
    result = None
    try:
        _download_file(url, dl, log)
        if not _verify_ollama_binary(dl, f"ollama-linux-{ollama_arch}.tar.zst", log):
            log("Ollama", "Binaire Linux rejete (SHA256 mismatch)", False)
            return None
        os.makedirs(BIN_DIR, exist_ok=True)
        _extract_tar_zst(dl, dl_bin, log)
        src = os.path.join(dl_bin, "bin", "ollama")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(BIN_DIR, "ollama"))
            os.chmod(os.path.join(BIN_DIR, "ollama"), 0o755)
        lib_dir = os.path.join(BASE_DIR, "lib", "ollama")
        os.makedirs(lib_dir, exist_ok=True)
        lib_src = os.path.join(dl_bin, "lib", "ollama")
        if os.path.exists(lib_src):
            for entry in os.listdir(lib_src):
                ep = os.path.join(lib_src, entry)
                dp = os.path.join(lib_dir, entry)
                subprocess.run(["cp", "-rL", ep, lib_dir], check=True, timeout=LAUNCHER_INSTALL_TIMEOUT) if os.path.isdir(ep) else shutil.copy2(ep, dp)
        result = os.path.join(BIN_DIR, "ollama")
    finally:
        if os.path.exists(dl_bin):
            shutil.rmtree(dl_bin, ignore_errors=True)
        if os.path.exists(dl):
            with contextlib.suppress(OSError):
                os.remove(dl)
    return result


def _install_windows_zip(log) -> str | None:
    log("Ollama", "Telechargement binaire Windows...")
    temp = os.environ.get("TEMP", "/tmp")
    url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-windows-amd64.zip"
    dl = os.path.join(temp, "ollama-windows.zip")
    dl_bin = os.path.join(temp, "ollama-extract")
    os.makedirs(dl_bin, exist_ok=True)
    _download_file(url, dl, log)
    if not _verify_ollama_binary(dl, "ollama-windows-amd64.zip", log):
        log("Ollama", "Archive Windows rejetee (SHA256 mismatch)", False)
        return None
    os.makedirs(BIN_DIR, exist_ok=True)
    with zipfile.ZipFile(dl, "r") as zf:
        zf.extractall(dl_bin)
    src = os.path.join(dl_bin, "ollama.exe")
    if os.path.exists(src):
        shutil.copy(src, os.path.join(BIN_DIR, "ollama.exe"))
    os.remove(dl)
    shutil.rmtree(dl_bin, ignore_errors=True)
    return os.path.join(BIN_DIR, "ollama.exe")


def _install_mac_brew(log) -> str | None:
    if not shutil.which("brew"):
        return None
    try:
        log("Ollama", "Installation via brew...")
        subprocess.run(["brew", "install", "ollama"], capture_output=True, timeout=LAUNCHER_WAIT_TIMEOUT)
        return shutil.which("ollama")
    except Exception as e:
        log("Ollama", f"Echec brew: {e}", False)
    return None


def _install_mac_script(log) -> str | None:
    try:
        log("Ollama", "Installation via script officiel...")
        r = subprocess.run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], capture_output=True, timeout=LAUNCHER_WAIT_TIMEOUT)
        if r.returncode == 0:
            return shutil.which("ollama")
        log("Ollama", "Echec install.sh", False)
    except Exception as e:
        log("Ollama", f"Echec installation macOS: {e}", False)
    return None


def _is_real_ollama(path: str) -> bool:
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
        return "ollama" in r.stdout.lower() or "ollama" in r.stderr.lower()
    except Exception as e:
        _logger.warning("Verification binaire Ollama echouee (%s): %s", path, e)
        return False


def ensure_ollama_binary(log) -> str | None:
    existing = get_ollama_path()
    if existing:
        if not _is_real_ollama(existing):
            log("Ollama", f"Binaire suspect: {existing}", False)
            return None
        return existing
    log("Ollama", "Binaire introuvable, tentative d'installation...")
    installers = {
        "linux":  [_install_linux_apt, _install_linux_tar],
        "darwin": [_install_mac_brew, _install_mac_script],
        "windows": [_install_windows_zip],
    }
    for install_fn in installers.get(SYSTEM, []):
        try:
            result = install_fn(log)
            if result:
                return result
        except Exception as e:
            log("Ollama", f"Echec {install_fn.__name__}: {e}", False)
    if SYSTEM == "windows":
        log("Ollama", "Telechargez manuellement depuis https://ollama.com/download/windows", False)
    return None
