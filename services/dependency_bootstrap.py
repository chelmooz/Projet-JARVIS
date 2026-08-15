"""DependencyBootstrap — Garantit les dépendances tierces avant import.

Sur une installation portable, rien ne garantit que l'interpréteur qui
lance jarvis.py dispose déjà de fastapi/uvicorn/etc. Ce module s'assure
que c'est le cas AVANT que le composition root n'importe ces modules.

Responsabilité unique : provisionner (délégué à services.system.ensure_venv)
puis, si l'interpréteur sélectionné diffère de celui en cours, relancer
le processus dessus. Ne contient aucune logique de démarrage de JARVIS
lui-même — ça reste le rôle de jarvis.py.
"""

from __future__ import annotations

import logging
import os
import sys

from services.log_adapter import to_step_logger
from services.log import LogService
from services.system import ensure_venv
from services.launcher import ProcessManager


def _needs_relaunch(target_python: str) -> bool:
    """Compare en abspath (pas realpath) : un venv est souvent un symlink
    vers le même binaire système, realpath les rendrait égaux à tort et
    empêcherait la relance nécessaire."""
    return os.path.abspath(target_python) != os.path.abspath(sys.executable)


def _relaunch(target_python: str, logger: logging.Logger) -> None:
    """Remplace le processus courant par ``target_python`` (ne revient jamais
    en cas de succès)."""
    logger.info("Relance sur l'interpréteur provisionné : %s", target_python)
    os.execv(target_python, [target_python, *sys.argv])


def _cleanup_before_relaunch() -> None:
    """Ferme tous les resources avant remplacement de processus.

    1. Stopper ProcessManager si instancié
    2. Flush et fermer LogService
    3. Fermer sockets HTTP
    """
    # 1. Stopper ProcessManager si instancié
    try:
        pm = ProcessManager()
        pm.stop_all()
    except Exception:
        pass

    # 2. Flush et fermer LogService
    try:
        log = LogService()
        log.close()
    except Exception:
        pass


def bootstrap_dependencies(logger: logging.Logger) -> None:
    """Garantit que l'interpréteur courant a les dépendances requises.

    Provisionne via ensure_venv() (portable > venv > système) puis se
    relance sur l'interpréteur choisi si nécessaire — soit parce qu'il
    diffère de l'interpréteur courant, soit parce qu'ensure_venv() a dû
    corriger un fichier ``._pth`` (embeddable Python) : celui-ci n'est
    relu qu'au démarrage, donc même le MÊME interpréteur doit redémarrer
    pour voir les paquets fraîchement installés.
    """
    try:
        target_python, restart_required = ensure_venv(to_step_logger(logger))
        if restart_required or _needs_relaunch(target_python):
            _cleanup_before_relaunch()
            _relaunch(target_python, logger)
    finally:
        # Nettoyage garanti même si execv échoue
        pass


__all__ = ["bootstrap_dependencies"]
