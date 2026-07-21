"""CommandExecutor — exécution isolée des outils de diagnostic externes.

Responsabilité unique (SRP) : construire la commande, lancer le subprocess et
normaliser le résultat/erreur. Délègue la vérification binaire (SHA256) et la
résolution de chemin à ses modules spécialisés (security / binary).
"""
import subprocess
import sys

from services.diagnostic_ext.audit import audit_log
from services.diagnostic_ext.binary import resolve_binary
from services.diagnostic_ext.security import verify_sha256

_MAX_STDOUT = 2000
_MAX_STDERR = 500
_MAX_ERROR = 200


class CommandExecutor:
    """Lance un outil externe et renvoie un dict normalisé."""

    def __init__(self, config: dict, bin_dir: str, log_service, verified: set):
        self._config = config
        self._bin_dir = bin_dir
        self._log = log_service
        self._verified = verified

    def run(self, tool_name: str, consent_given: bool,
            args: list[str] | None = None,
            extra_kwargs: dict | None = None) -> dict:
        """Exécute l'outil ou renvoie un dict d'erreur court-circuité."""
        if not consent_given:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: consentement non donne")
            return {"success": False, "tool": tool_name, "error": "Consentement non donne"}
        cfg = self._config.get("tools", {}).get(tool_name)
        if not cfg:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: outil inconnu")
            return {"success": False, "tool": tool_name, "error": f"Outil '{tool_name}' inconnu"}
        path = resolve_binary(self._config, tool_name, self._bin_dir)
        if not path:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: binaire introuvable")
            return {"success": False, "tool": tool_name,
                    "error": f"Binaire introuvable pour {tool_name}"}
        sha = cfg.get("sha256", "")
        if sha and not self._verify(tool_name, path, sha):
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: echec SHA256")
            return {"success": False, "tool": tool_name, "error": "Echec verification SHA256"}
        cmd_args = self.build_args(cfg, args, extra_kwargs)
        return self._execute(tool_name, path, cmd_args, cfg.get("timeout", 10))

    def build_args(self, cfg: dict, args: list[str] | None,
                   extra_kwargs: dict | None) -> list[str]:
        """Construit la liste d'arguments (plateforme + formatting kwargs)."""
        if args is None:
            args = (list(cfg.get("args", [])) if sys.platform == "win32"
                    else list(cfg.get("linux_args", cfg.get("args", []))))
        if extra_kwargs:
            args = [a.format(**extra_kwargs) for a in args]
        return args

    @staticmethod
    def format_result(tool_name: str, proc: subprocess.CompletedProcess) -> dict:
        """Normalise un subprocess réussi en dict de résultat."""
        return {
            "success": proc.returncode == 0,
            "tool": tool_name,
            "stdout": proc.stdout.strip()[:_MAX_STDOUT],
            "stderr": proc.stderr.strip()[:_MAX_STDERR],
            "returncode": proc.returncode,
        }

    def _verify(self, tool_name: str, path: str, sha: str) -> bool:
        return verify_sha256(
            tool_name, path, sha, self._verified,
            lambda level, msg: audit_log(self._log, level, msg),
        )

    def _execute(self, tool_name: str, path: str, args: list[str], timeout: int) -> dict:
        audit_log(self._log, "INFO", f"AUDIT tool={tool_name} args={args}")
        try:
            result = subprocess.run(
                [path] + args, capture_output=True, text=True, timeout=timeout,
            )
            return self.format_result(tool_name, result)
        except subprocess.TimeoutExpired:
            audit_log(self._log, "WARN", f"Timeout {tool_name} apres {timeout}s")
            return {"success": False, "tool": tool_name, "error": f"Timeout ({timeout}s)"}
        except FileNotFoundError:
            return {"success": False, "tool": tool_name, "error": f"Binaire introuvable: {path}"}
        except Exception as e:
            audit_log(self._log, "ERROR", f"Echec {tool_name}: {e}")
            return {"success": False, "tool": tool_name, "error": str(e)[:_MAX_ERROR]}
