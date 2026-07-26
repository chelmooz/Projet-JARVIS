# tests/test_security_format_string.py
r"""Tests de sécurité — Format string injection dans CommandExecutor.build_args()

Vulnérabilité corrigée :
- Substitution chaînée de second ordre (boucle .replace() successive)
- Aucune whitelist de clés autorisées
- Aucune validation de valeur (longueur, charset)

Comportement attendu après correction :
- Substitution en UNE seule passe
- Clés limitées à cfg.get("allowed_params", [])
- Valeurs validées par regex ^[A-Za-z0-9_.\-]{1,128}$
- Absence de allowed_params = liste vide (fail-safe)
"""
from unittest.mock import MagicMock, patch

import pytest


class TestCommandExecutorBuildArgs:
    """Tests de sécurité pour CommandExecutor.build_args() — format string injection."""

    @pytest.fixture
    def executor(self):
        """Instance de CommandExecutor avec dépendances mockées."""
        from services.diagnostic_ext.executor import CommandExecutor
        return CommandExecutor(
            config={},
            bin_dir=".",
            log_service=MagicMock(),
            verified=set()
        )

    @pytest.fixture
    def mock_audit_log(self):
        """Mock de la fonction libre audit_log."""
        with patch("services.diagnostic_ext.executor.audit_log") as mock_log:
            yield mock_log

    def test_build_args_rejette_substitution_chainee(self, executor, mock_audit_log):
        """
        Cas A : Substitution chaînée de second ordre doit être rejetée.

        Scénario : extra_kwargs = {"a": "{b}", "b": "PAYLOAD"}
        Attendu : L'arg résultant contient littéralement "{b}", jamais "PAYLOAD".

        Vulnérabilité actuelle : la boucle .replace() successive substitue "{b}"
        dans la valeur de "a", puis substitue "{b}" par "PAYLOAD" au tour suivant.
        """
        cfg = {"allowed_params": ["a", "b"]}
        args = ["--flag={a}"]
        extra_kwargs = {"a": "{b}", "b": "PAYLOAD"}

        result = executor.build_args(cfg, args, extra_kwargs)

        # Le résultat doit contenir littéralement "{b}", pas "PAYLOAD"
        assert len(result) == 1
        assert result[0] == "--flag={b}", \
            f"Substitution chaînée détectée : attendu '--flag={{b}}', obtenu '{result[0]}'"
        assert "PAYLOAD" not in result[0], \
            "Vulnérabilité : substitution chaînée a injecté 'PAYLOAD'"

    def test_build_args_ignore_cle_hors_whitelist(self, executor, mock_audit_log):
        """
        Cas B : Clé absente de allowed_params → placeholder non substitué + log WARN.

        Scénario : cfg.allowed_params = ["safe_param"], extra_kwargs = {"unknown_key": "value"}
        Attendu : Le placeholder "{unknown_key}" reste tel quel, audit_log appelé.
        """
        cfg = {"allowed_params": ["safe_param"]}
        args = ["--flag={unknown_key}"]
        extra_kwargs = {"unknown_key": "value"}

        result = executor.build_args(cfg, args, extra_kwargs)

        # Le placeholder doit rester non substitué
        assert len(result) == 1
        assert result[0] == "--flag={unknown_key}", \
            f"Clé hors whitelist substituée : attendu '--flag={{unknown_key}}', obtenu '{result[0]}'"

        # Un log d'audit WARN doit avoir été émis
        mock_audit_log.assert_called()
        # Vérifie qu'au moins un appel contient "WARN" et mentionne la clé
        calls = mock_audit_log.call_args_list
        assert any(
            len(call.args) >= 2 and call.args[1] == "WARN" and "unknown_key" in str(call.args[2])
            for call in calls
        ), "Log d'audit ne mentionne pas la clé hors whitelist"

    def test_build_args_rejette_valeur_invalide(self, executor, mock_audit_log):
        """
        Cas C : Valeur invalide (path traversal, injection shell) → substitution refusée.

        Scénarios :
        - value = "../../etc/passwd" → rejeté (caractères '/' non autorisés)
        - value = "x; rm -rf" → rejeté (caractères ';' et espaces non autorisés)

        Attendu : Placeholder brut conservé, log WARN émis.
        """
        # Test 1 : Path traversal
        cfg = {"allowed_params": ["path"]}
        args1 = ["--file={path}"]
        extra_kwargs1 = {"path": "../../etc/passwd"}

        result1 = executor.build_args(cfg, args1, extra_kwargs1)

        assert len(result1) == 1
        assert result1[0] == "--file={path}", \
            f"Valeur invalide substituée : attendu '--file={{path}}', obtenu '{result1[0]}'"
        mock_audit_log.assert_called()

        # Reset du mock pour le second test
        mock_audit_log.reset_mock()

        # Test 2 : Injection shell
        cfg2 = {"allowed_params": ["command"]}
        args2 = ["--cmd={command}"]
        extra_kwargs2 = {"command": "x; rm -rf"}

        result2 = executor.build_args(cfg2, args2, extra_kwargs2)

        assert len(result2) == 1
        assert result2[0] == "--cmd={command}", \
            f"Valeur invalide substituée : attendu '--cmd={{command}}', obtenu '{result2[0]}'"
        mock_audit_log.assert_called()

    def test_build_args_substitution_ok_inchangee(self, executor, mock_audit_log):
        """
        Cas D : Cas nominal inchangé — clé whitelistée, valeur safe.

        Scénario : cfg.allowed_params = ["safe_param", "another_safe"]
                   extra_kwargs = {"safe_param": "valid_value", "another_safe": "test123"}
        Attendu : Comportement identique à l'actuel, substitution réussie, aucun log WARN.
        """
        cfg = {"allowed_params": ["safe_param", "another_safe"]}
        args = ["--flag={safe_param} --other={another_safe}"]
        extra_kwargs = {"safe_param": "valid_value", "another_safe": "test123"}

        result = executor.build_args(cfg, args, extra_kwargs)

        # Les deux placeholders doivent être substitués
        assert len(result) == 1
        assert result[0] == "--flag=valid_value --other=test123", \
            f"Substitution nominale échouée : attendu '--flag=valid_value --other=test123', obtenu '{result[0]}'"

        # Aucun log WARN ne doit avoir été émis (cas nominal)
        # Vérifie qu'aucun appel n'a "WARN" comme second argument
        calls = mock_audit_log.call_args_list
        assert not any(
            len(call.args) >= 2 and call.args[1] == "WARN"
            for call in calls
        ), "Log WARN émis alors que le cas est nominal"

    def test_build_args_fail_safe_no_whitelist(self, executor, mock_audit_log):
        """
        Cas E (bonus) : Absence de allowed_params dans la config = fail-safe.

        Scénario : cfg = {} (pas de clé "allowed_params")
        Attendu : Aucun placeholder n'est substitué, tous les logs WARN émis.
        """
        cfg = {}  # Pas de "allowed_params" → fail-safe
        args = ["--flag={safe_param}"]
        extra_kwargs = {"safe_param": "valid_value"}

        result = executor.build_args(cfg, args, extra_kwargs)

        # Même une clé "safe" doit être rejetée si whitelist vide
        assert len(result) == 1
        assert result[0] == "--flag={safe_param}", \
            f"Fail-safe violé : whitelist vide mais substitution effectuée '{result[0]}'"

        mock_audit_log.assert_called()
