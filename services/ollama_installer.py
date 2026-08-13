"""OllamaInstaller — Installation du binaire Ollama.

Extrait de services/launcher.py (refactor Q4).
Responsabilités :
  - Installation plateforme (apt, tar, zip, brew, script)
  - Point d'entrée unique ensure_ollama_binary
  - Délègue téléchargement et vérification SHA256 à services.ollama_download
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import shutil
import stat
import subprocess
import zipfile
from collections.abc import Callable

from config.constants import (
    LAUNCHER_INSTALL_TIMEOUT,
    LAUNCHER_WAIT_TIMEOUT,
    OLLAMA_VERSION,
)
from services.ollama_download import (
    _download_file,
    _verify_ollama_binary,
)
from services.system import BASE_DIR, BIN_DIR, BIN_LINUX, SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.ollama_installer")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _install_linux_apt(log: _LogFn) -> str | None:
    """Tente d'installer Ollama via apt (Debian/Ubuntu)."""
    try:
        log("Ollama", "Tentative apt install ollama...", None)
        r = subprocess.run(
            ["apt", "install", "-y", "ollama"], capture_output=True, text=True, timeout=LAUNCHER_INSTALL_TIMEOUT
        )
        if r.returncode == 0:
            return shutil.which("ollama")
    except Exception as e:
        log("Ollama", "apt introuvable ou échec", False)
        _logger.debug("Échec apt install ollama : %s", e)
    return None


def _extract_tar_zst(archive: str, dest_dir: str, log: _LogFn) -> None:
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
        _logger.debug("Échec tar --zstd : %s", e)
        subprocess.run(["tar", "-xf", archive, "-C", dest_dir], check=True, timeout=LAUNCHER_WAIT_TIMEOUT)


def _install_linux_tar(log: _LogFn) -> str | None:
    """Télécharge et installe le binaire Linux depuis GitHub."""
    log("Ollama", "Téléchargement binaire Linux...", None)
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
            log("Ollama", "Binaire Linux rejeté (SHA256 mismatch)", False)
            return None

        os.makedirs(BIN_LINUX, exist_ok=True)
        _extract_tar_zst(dl, dl_bin, log)

        src = os.path.join(dl_bin, "bin", "ollama")
        if os.path.exists(src):
            dest_bin = os.path.join(BIN_LINUX, "ollama")
            shutil.copy(src, dest_bin)
            os.chmod(dest_bin, 0o755)

        lib_dir = os.path.join(BASE_DIR, "lib", "ollama")
        os.makedirs(lib_dir, exist_ok=True)
        lib_src = os.path.join(dl_bin, "lib", "ollama")

        if os.path.exists(lib_src):
            for entry in os.listdir(lib_src):
                ep = os.path.join(lib_src, entry)
                dp = os.path.join(lib_dir, entry)
                if os.path.isdir(ep):
                    subprocess.run(["cp", "-rL", ep, lib_dir], check=True, timeout=LAUNCHER_INSTALL_TIMEOUT)
                else:
                    shutil.copy2(ep, dp)

        # ✅ CORRECTION PHASE 6.1 : Retourne le chemin correct pour Linux (BIN_LINUX)
        result = os.path.join(BIN_LINUX, "ollama")
    finally:
        if os.path.exists(dl_bin):
            shutil.rmtree(dl_bin, ignore_errors=True)
        if os.path.exists(dl):
            with contextlib.suppress(OSError):
                os.remove(dl)

    return result


def _safe_extract_zip(archive: str, dest_dir: str) -> None:
    """Extrait une archive ZIP sans autoriser de sortie du répertoire cible.

    Les archives ZIP malveillantes peuvent contenir des chemins ``../`` ou des
    liens symboliques. Ces entrées sont refusées avant toute écriture pour
    préserver le support portable et le poste hôte.
    """
    destination = os.path.realpath(dest_dir)
    with zipfile.ZipFile(archive, "r") as zf:
        for entry in zf.infolist():
            target = os.path.realpath(os.path.join(destination, entry.filename))
            try:
                is_within_destination = os.path.commonpath([destination, target]) == destination
            except ValueError:
                is_within_destination = False
            is_symlink = stat.S_ISLNK(entry.external_attr >> 16)
            if not is_within_destination or is_symlink:
                raise ValueError(f"Entrée ZIP non sûre refusée : {entry.filename}")
        zf.extractall(destination)


def _install_windows_zip(log: _LogFn) -> str | None:
    """Télécharge et installe le binaire Windows depuis GitHub."""
    log("Ollama", "Téléchargement binaire Windows...", None)
    temp = os.environ.get("TEMP", "/tmp")
    url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-windows-amd64.zip"
    dl = os.path.join(temp, "ollama-windows.zip")
    dl_bin = os.path.join(temp, "ollama-extract")
    os.makedirs(dl_bin, exist_ok=True)

    try:
        _download_file(url, dl, log)
        if not _verify_ollama_binary(dl, "ollama-windows-amd64.zip", log):
            log("Ollama", "Archive Windows rejetée (SHA256 mismatch)", False)
            return None

        os.makedirs(BIN_DIR, exist_ok=True)
        _safe_extract_zip(dl, dl_bin)

        src = os.path.join(dl_bin, "ollama.exe")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(BIN_DIR, "ollama.exe"))

        # CORRECTION : l'archive Windows contient aussi lib/ollama/ (llama-server.exe,
        # DLL GPU) — sans cette copie, ollama.exe démarre mais ne trouve jamais le
        # moteur d'inférence ("failure during llama-server GPU discovery"). On
        # reproduit ici la même logique que _install_linux_tar (lib/ollama copié
        # sous BASE_DIR/lib/ollama, un des chemins qu'Ollama sonde nativement).
        lib_src = os.path.join(dl_bin, "lib", "ollama")
        if os.path.exists(lib_src):
            lib_dest = os.path.join(BASE_DIR, "lib", "ollama")
            # Etape silencieuse sinon (aucun log() pendant shutil.copytree) — sur
            # cle USB (I/O lente, fichiers un par un) cela ressemble a un gel.
            log("Ollama", f"Copie du moteur d'inference ({lib_src} -> {lib_dest})...", None)
            shutil.copytree(lib_src, lib_dest, dirs_exist_ok=True)
            log("Ollama", "Moteur d'inference copie", True)

        return os.path.join(BIN_DIR, "ollama.exe")
    finally:
        if os.path.exists(dl):
            with contextlib.suppress(OSError):
                os.remove(dl)
        if os.path.exists(dl_bin):
            shutil.rmtree(dl_bin, ignore_errors=True)


def _install_mac_brew(log: _LogFn) -> str | None:
    """Tente d'installer Ollama via Homebrew (macOS)."""
    if not shutil.which("brew"):
        return None
    try:
        log("Ollama", "Installation via brew...", None)
        subprocess.run(["brew", "install", "ollama"], capture_output=True, timeout=LAUNCHER_WAIT_TIMEOUT)
        return shutil.which("ollama")
    except Exception as e:
        log("Ollama", f"Échec brew : {e}", False)
    return None


def _install_mac_script(log: _LogFn) -> str | None:
    """Refuse l'exécution automatique d'un script distant sur macOS.

    Le produit promet une exécution portable qui ne modifie pas le poste hôte.
    Exécuter ``curl | sh`` contredit cette promesse et ne permet pas de vérifier
    l'intégrité de ce qui est exécuté. L'utilisateur doit installer Ollama par
    le canal officiel de son choix, puis relancer JARVIS.
    """
    log(
        "Ollama",
        "Installation macOS automatique désactivée : aucun script réseau n'est exécuté.",
        False,
    )
    return None


def _is_real_ollama(path: str) -> bool:
    """Vérifie que le binaire est bien Ollama et pas un faux positif."""
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
        return "ollama" in r.stdout.lower() or "ollama" in r.stderr.lower()
    except Exception as e:
        _logger.warning("Vérification binaire Ollama échouée (%s) : %s", path, e)
        return False


def ensure_ollama_binary(log: _LogFn) -> str | None:
    """Point d'entrée unique : vérifie ou installe le binaire Ollama."""
    existing = get_ollama_path()
    if existing:
        if not _is_real_ollama(existing):
            log("Ollama", f"Binaire suspect ou corrompu : {existing}", False)
            return None
        return existing

    log("Ollama", "Binaire introuvable, tentative d'installation...", None)
    installers = {
        # JARVIS reste portable : aucune installation système (apt, brew ou
        # script distant) n'est lancée automatiquement sur le poste hôte.
        "linux": [_install_linux_tar],
        "darwin": [_install_mac_script],
        "windows": [_install_windows_zip],
    }

    for install_fn in installers.get(SYSTEM, []):
        try:
            result = install_fn(log)
            if result:
                return result
        except Exception as e:
            log("Ollama", f"Échec {install_fn.__name__} : {e}", False)

    if SYSTEM == "windows":
        log("Ollama", "Téléchargez manuellement depuis https://ollama.com/download/windows", False)

    return None


__all__ = ["ensure_ollama_binary"]
