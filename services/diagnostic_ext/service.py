"""DiagnosticExtService — orchestre l'exécution des outils de diagnostic externes.

Responsabilités :
- Résolution et vérification SHA256 des binaires externes.
- Délégation de l'exécution à CommandExecutor (SRP).
- Orchestration des outils : smartctl, psinfo, psloglist, handle, psping, psservice, witr.

(C1 — le consentement utilisateur a été retiré : usage mono-utilisateur,
aucun gate de permission.)

Dettes signalées (non corrigées ici) :
- ``list_available()`` et ``is_ready()`` appellent ``check_all_tools()`` à chaque
  invocation (résolution binaire + vérification SHA256). Pas de cache : coûteux
  si appelé fréquemment. Un cache TTL (ex: 60s) serait pertinent si les outils
  ne sont pas ajoutés/retirés dynamiquement.
"""

from __future__ import annotations

import sys
from typing import Any

from services.diagnostic_ext.audit import audit_log
from services.diagnostic_ext.binary import resolve_binary, resolve_expected_sha256
from services.diagnostic_ext.config import (
    BIN_DIR,
    CONFIG_PATH,
    default_smart_device,
    get_tools_config,
    load_config,
)
from services.diagnostic_ext.executor import CommandExecutor
from services.diagnostic_ext.security import verify_sha256


class DiagnosticExtService:
    """Orchestre les outils de diagnostic externes (Sysinternals, smartctl, etc.).

    Vérifie l'intégrité (SHA256) et délègue l'exécution à CommandExecutor.
    """

    def __init__(
        self,
        config_path: str = CONFIG_PATH,
        bin_dir: str = BIN_DIR,
        log_service: Any | None = None,
    ) -> None:
        self._config_path = config_path
        self._bin_dir = bin_dir
        self._log = log_service
        self._config = load_config(self._config_path)
        self._verified: set[str] = set()

    def get_tools_config(self) -> dict[str, Any]:
        """Retourne la configuration des outils (section ``tools`` du config)."""
        return get_tools_config(self._config)

    def _run_tool(
        self,
        tool_name: str,
        args: list[str] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Exécute un outil externe (délègue au CommandExecutor, SRP)."""
        executor = CommandExecutor(
            self._config,
            self._bin_dir,
            self._log,
            self._verified,
        )
        return executor.run(tool_name, args, extra_kwargs)

    def run_smartctl(self, device: str | None = None) -> dict[str, Any]:
        """Exécute smartctl sur le device spécifié (défaut: auto-détecté)."""
        if device is None:
            device = default_smart_device()
        return self._run_tool("smartctl", extra_kwargs={"device": device})

    def run_psinfo(self) -> dict[str, Any]:
        """Exécute psinfo (informations système)."""
        return self._run_tool("psinfo")

    def run_psloglist(self, log_name: str = "System") -> dict[str, Any]:
        """Exécute psloglist pour lire les logs Windows."""
        return self._run_tool("psloglist", extra_kwargs={"log_name": log_name})

    def run_handle(self, pattern: str = "") -> dict[str, Any]:
        """Exécute handle pour lister les handles ouverts (filtrage par pattern)."""
        return self._run_tool("handle", extra_kwargs={"pattern": pattern})

    def run_psping(self, target: str = "127.0.0.1", count: str = "4") -> dict[str, Any]:
        """Exécute psping pour tester la latence réseau."""
        return self._run_tool("psping", extra_kwargs={"target": target, "count": count})

    def run_psservice(self, service_name: str = "") -> dict[str, Any]:
        """Exécute psservice pour gérer les services Windows."""
        return self._run_tool("psservice", extra_kwargs={"service_name": service_name})

    def run_witr(self, target: str) -> dict[str, Any]:
        """Explique pourquoi un process/port/service `target` tourne (via witr --json).

        Un target purement numérique est traité comme un **port** (witr exige
        ``--port`` pour une requête port ; les positionnels witr sont des noms
        de process). Tout autre target est un nom de process / service /
        conteneur (positionnel).
        """
        kwargs = {"port": target} if target.isdigit() else {"target": target}
        return self._run_tool("witr", extra_kwargs=kwargs)

    def _check_tool(self, name: str) -> dict[str, Any]:
        """Vérifie la disponibilité et l'intégrité d'un outil unique."""
        path = resolve_binary(self._config, name, self._bin_dir)
        cfg = self._config["tools"][name]
        sha = resolve_expected_sha256(self._config, name, sys.platform)
        sha_ok = False
        if path and sha:
            sha_ok = verify_sha256(
                name,
                path,
                sha,
                self._verified,
                lambda level, msg: audit_log(self._log, level, msg),
            )
        return {
            "available": path is not None,
            "path": path,
            "sha256_ok": sha_ok,
            "platforms": cfg.get("platforms", []),
        }

    def check_all_tools(self) -> dict[str, dict[str, Any]]:
        """Vérifie la disponibilité et l'intégrité de tous les outils configurés."""
        return {name: self._check_tool(name) for name in self._config.get("tools", {})}

    def list_available(self) -> list[str]:
        """Liste les outils disponibles (binaires présents + SHA256 valide)."""
        return [name for name, info in self.check_all_tools().items() if info["available"] and info["sha256_ok"]]

    def is_ready(self) -> bool:
        """Vérifie si le service est prêt (au moins un outil disponible)."""
        return len(self.list_available()) > 0


__all__ = ["DiagnosticExtService"]
