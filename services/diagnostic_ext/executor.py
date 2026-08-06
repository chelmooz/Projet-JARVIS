"""CommandExecutor — exécution isolée des outils de diagnostic externe.
Responsabilité unique (SRP) : construire la commande, lancer le subprocess et
normaliser le résultat/erreur. Délègue la vérification binaire (SHA256) et la
résolution de chemin à ses modules spécialisés (security / binary).
"""
from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from services.diagnostic_ext.audit import audit_log
from services.diagnostic_ext.binary import resolve_binary, resolve_expected_sha256
from services.diagnostic_ext.formatters import get_formatter
from services.diagnostic_ext.security import verify_sha256

_MAX_ERROR = 200

# Regex pour détecter les placeholders {key} dans les templates
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")

# Regex pour valider les valeurs substituées (charset strict, max 128 chars)
# Les accolades {} et le deux-points : sont autorisés car la substitution
# est en passe unique (pas de re-scan), donc une valeur contenant "{autre_clé}"
# reste littérale. Le ':' est autorisé pour les chemins Windows (ex: "C:").
_VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-{}:]{1,128}$")


class CommandExecutor:
    """Lance un outil externe et renvoie un dict normalisé."""

    def __init__(
        self,
        config: dict[str, Any],
        bin_dir: str,
        log_service: Any,
        verified: set[str],
    ) -> None:
        self._config = config
        self._bin_dir = bin_dir
        self._log = log_service
        self._verified = verified

    def run(
        self,
        tool_name: str,
        consent_given: bool,
        args: list[str] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Exécute l'outil ou renvoie un dict d'erreur court-circuité."""
        if not consent_given:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: consentement non donné")
            return {"success": False, "tool": tool_name, "error": "Consentement non donné"}

        cfg = self._config.get("tools", {}).get(tool_name)
        if not cfg:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: outil inconnu")
            return {"success": False, "tool": tool_name, "error": f"Outil '{tool_name}' inconnu"}

        path = resolve_binary(self._config, tool_name, self._bin_dir)
        if not path:
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: binaire introuvable")
            return {"success": False, "tool": tool_name, "error": f"Binaire introuvable pour {tool_name}"}

        sha = resolve_expected_sha256(self._config, tool_name, sys.platform)
        if sha and not self._verify(tool_name, path, sha):
            audit_log(self._log, "WARN", f"AUDIT tool={tool_name}: échec SHA256")
            return {"success": False, "tool": tool_name, "error": "Échec vérification SHA256"}

        cmd_args = self.build_args(cfg, args, extra_kwargs)
        formatter = get_formatter(cfg.get("output_format", "text"))
        return self._execute(tool_name, path, cmd_args, cfg.get("timeout", 10), formatter)

    def build_args(
        self,
        cfg: dict[str, Any],
        args: list[str] | None,
        extra_kwargs: dict[str, Any] | None,
    ) -> list[str]:
        """Construit la liste d'arguments (plateforme + formatting kwargs sécurisés).
        Sécurité : substitution en UNE seule passe via re.sub, avec whitelist
        de clés autorisées (cfg["allowed_params"]) et validation de valeur
        par regex stricte. Élimine les vulnérabilités de substitution chaînée
        et d'injection de format string.

        Si les kwargs contiennent une clé ``port``, le template ``port_args``
        (indépendant de la plateforme, ex: witr ``--port``) remplace les args
        nommés — les positionnels witr sont des noms, pas des ports.
        """
        uses_port = bool(extra_kwargs) and "port" in extra_kwargs
        if args is None:
            if uses_port:
                args = list(cfg.get("port_args", cfg.get("args", [])))
            else:
                args = (
                    list(cfg.get("args", []))
                    if sys.platform == "win32"
                    else list(cfg.get("linux_args", cfg.get("args", [])))
                )

        # Si pas de kwargs extra, retour direct (pas de régression)
        if not extra_kwargs:
            return args

        # Whitelist de clés autorisées (fail-safe : liste vide si absente)
        whitelist = set(cfg.get("allowed_params", []))

        # Construction du dict de substitutions validées
        substitutions: dict[str, str] = {}
        for key, value in extra_kwargs.items():
            # Vérification 1 : clé dans whitelist
            if key not in whitelist:
                audit_log(
                    self._log,
                    "WARN",
                    f"build_args: clé hors whitelist ignorée: {key}"
                )
                continue

            # Vérification 2 : valeur valide selon regex stricte
            str_value = str(value)
            if not _VALUE_RE.match(str_value):
                audit_log(
                    self._log,
                    "WARN",
                    f"build_args: valeur invalide rejetée pour clé {key}"
                )
                continue

            substitutions[key] = str_value

        # Substitution en UNE seule passe via re.sub (pas de boucle .replace)
        def callback(match: re.Match) -> str:
            key = match.group(1)
            # Si la clé est dans substitutions, on retourne la valeur validée
            # Sinon, on retourne le placeholder original (ex: "{unknown_key}")
            return substitutions.get(key, match.group(0))

        return [_PLACEHOLDER_RE.sub(callback, a) for a in args]

    @staticmethod
    def format_result(
        tool_name: str, proc: subprocess.CompletedProcess[str], output_format: str = "text"
    ) -> dict[str, Any]:
        """Normalise un subprocess réussi en dict de résultat (délègue au formatter).

        Conserve la signature historique avec ``output_format`` par défaut
        ``text`` pour compatibilité (retirée lors du refacto stratégie).
        """
        return get_formatter(output_format).format(tool_name, proc)

    def _verify(self, tool_name: str, path: str, sha: str) -> bool:
        """Vérifie le hash SHA256 du binaire."""
        return verify_sha256(
            tool_name,
            path,
            sha,
            self._verified,
            lambda level, msg: audit_log(self._log, level, msg),
        )

    def _execute(
        self,
        tool_name: str,
        path: str,
        args: list[str],
        timeout: int,
        formatter: Any,
    ) -> dict[str, Any]:
        """Exécute le subprocess et gère les erreurs (timeout, fichier introuvable)."""
        audit_log(self._log, "INFO", f"AUDIT tool={tool_name} args={args}")
        try:
            result = subprocess.run(
                [path] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return formatter.format(tool_name, result)
        except subprocess.TimeoutExpired:
            audit_log(self._log, "WARN", f"Timeout {tool_name} après {timeout}s")
            return {"success": False, "tool": tool_name, "error": f"Timeout ({timeout}s)"}
        except FileNotFoundError:
            return {"success": False, "tool": tool_name, "error": f"Binaire introuvable: {path}"}
        except Exception as e:
            audit_log(self._log, "ERROR", f"Échec {tool_name}: {e}")
            return {"success": False, "tool": tool_name, "error": str(e)[:_MAX_ERROR]}


__all__ = ["CommandExecutor"]
