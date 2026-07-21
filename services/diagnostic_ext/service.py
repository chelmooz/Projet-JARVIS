"""DiagnosticExtService — orchestre l'exécution des outils de diagnostic externes."""
import os
import time

from services.diagnostic_ext.audit import audit_log
from services.diagnostic_ext.binary import resolve_binary
from services.diagnostic_ext.config import (
    BIN_DIR,
    CONFIG_PATH,
    CONSENT_FILE,
    default_smart_device,
    get_tools_config,
    load_config,
)
from services.diagnostic_ext.executor import CommandExecutor
from services.diagnostic_ext.security import verify_sha256


class DiagnosticExtService:
    """DiagnosticExtService."""

    def __init__(self, config_path: str = CONFIG_PATH, bin_dir: str = BIN_DIR,
                 consent_file: str = CONSENT_FILE, log_service=None):
        self._config_path = config_path
        self._bin_dir = bin_dir
        self._consent_file = consent_file
        self._log = log_service
        self._config = load_config(self._config_path)
        self._consent_given = os.path.exists(self._consent_file)
        self._verified = set()

    def get_tools_config(self) -> dict:
        return get_tools_config(self._config)

    def ensure_consent(self) -> tuple[bool, str]:
        if self._consent_given:
            return True, "Consentement deja donne"
        return False, ("Consentement requis. Lancez d'abord : "
                       f"echo 'consent' > {self._consent_file}")

    def grant_consent(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self._consent_file), exist_ok=True)
            with open(self._consent_file, "w") as f:
                f.write(f"consent granted {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
            self._consent_given = True
            audit_log(self._log, "CONSENT", "Consentement diagnostic accorde")
            return True
        except Exception as e:
            audit_log(self._log, "ERROR", f"Echec consentement: {e}")
            return False

    def _run_tool(self, tool_name: str, args: list[str] | None = None,
                  extra_kwargs: dict | None = None) -> dict:
        """Exécute un outil externe (délègue au CommandExecutor, SRP)."""
        executor = CommandExecutor(
            self._config, self._bin_dir, self._log, self._verified,
        )
        return executor.run(tool_name, self._consent_given, args, extra_kwargs)

    def run_smartctl(self, device: str = None) -> dict:
        if device is None:
            device = default_smart_device()
        return self._run_tool("smartctl", extra_kwargs={"device": device})

    def run_psinfo(self) -> dict:
        return self._run_tool("psinfo")

    def run_psloglist(self, log_name: str = "System") -> dict:
        return self._run_tool("psloglist", extra_kwargs={"log_name": log_name})

    def run_handle(self, pattern: str = "") -> dict:
        return self._run_tool("handle", extra_kwargs={"pattern": pattern})

    def run_psping(self, target: str = "127.0.0.1", count: str = "4") -> dict:
        return self._run_tool("psping", extra_kwargs={"target": target, "count": count})

    def run_psservice(self, service_name: str = "") -> dict:
        return self._run_tool("psservice", extra_kwargs={"service_name": service_name})

    def check_all_tools(self) -> dict[str, dict]:
        results = {}
        for name in self._config.get("tools", {}):
            path = resolve_binary(self._config, name, self._bin_dir)
            cfg = self._config["tools"][name]
            sha = cfg.get("sha256", "")
            sha_ok = False
            if path and sha:
                sha_ok = verify_sha256(name, path, sha, self._verified,
                                       lambda level, msg: audit_log(self._log, level, msg))
            results[name] = {
                "available": path is not None,
                "path": path,
                "sha256_ok": sha_ok,
                "platforms": cfg.get("platforms", []),
            }
        return results

    def list_available(self) -> list[str]:
        return [name for name, info in self.check_all_tools().items()
                if info["available"] and info["sha256_ok"]]

    def is_ready(self) -> bool:
        if not self._consent_given:
            return False
        return len(self.list_available()) > 0
