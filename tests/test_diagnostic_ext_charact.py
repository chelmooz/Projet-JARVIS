"""Tests de caractérisation — figent le comportement ACTUEL avant refacto.

Objectif (Phase 0) : garantir zéro régression pendant les refactos de la
Phase 2 (resolve_binary OS-aware) et Phase 4 (output_format text/json).
Ces tests documentent le contrat actuel : structure de sortie, troncatures,
résolution de binaire flat, whitelist build_args. Ils ne testent PAS le
comportement cible, ils verrouillent le comportement existant.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest.mock as mock

import yaml

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.diagnostic_ext import DiagnosticExtService  # noqa: E402
from services.diagnostic_ext.binary import resolve_binary  # noqa: E402
from services.diagnostic_ext.executor import CommandExecutor  # noqa: E402
from services.diagnostic_ext.formatters import (  # noqa: E402
    JsonResultFormatter,
    TextResultFormatter,
    get_formatter,
)

# Constantes du module executor (à refléter, pas à importer : elles peuvent
# changer de forme pendant le refacto — le test doit rester valide).
_STDOUT_LIMIT = 2000
_STDERR_LIMIT = 500

SAMPLE_CONFIG = {
    "tools": {
        "smartctl": {
            "binary": "smartctl.exe",
            "linux_binary": "smartctl",
            "description": "SMART disk health",
            "timeout": 5,
            "platforms": ["win32", "linux"],
            "args": ["-a", "{device}"],
            "linux_args": ["-a", "{device}"],
            "allowed_params": ["device"],
            "sha256": "E38945652D86A4B0CDFEE8A63EE2737F2026A68D4C164A3B7C78EDC10B807507",
        },
        "psinfo": {
            "binary": "PsInfo64.exe",
            "description": "System information",
            "timeout": 5,
            "platforms": ["win32"],
            "args": ["-s", "-d"],
            "sha256": "DE73B73EEB156F877DE61F4A6975D06759292ED69F31AAF06C9811F3311E03E7",
        },
    },
}


class FakeLog:
    def __init__(self):
        self.entries = []

    def log(self, level, message):
        self.entries.append({"level": level, "message": message})


def _platform_subdir() -> str:
    """Sous-dossier de bin_dir attendu par la plateforme courante (Phase 2)."""
    return {"win32": "win", "linux": "linux", "darwin": "darwin"}.get(
        sys.platform, sys.platform
    )


def _make_executor(tmpdir, config=None, bin_dir=None, log_service=None):
    """Construit un CommandExecutor avec une config temporaire."""
    bin_dir = bin_dir or os.path.join(tmpdir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    return CommandExecutor(
        config=config or SAMPLE_CONFIG,
        bin_dir=bin_dir,
        log_service=log_service or FakeLog(),
        verified=set(),
    )


class TestFormatResult:
    """Caractérise `CommandExecutor.format_result` (contrat actuel)."""

    def _proc(self, stdout="out", stderr="err", returncode=0):
        return subprocess.CompletedProcess(args=["tool"], returncode=returncode,
                                           stdout=stdout, stderr=stderr)

    def test_structure_du_dict_normalise(self):
        result = CommandExecutor.format_result("smartctl", self._proc())
        assert set(result) == {"success", "tool", "stdout", "stderr", "returncode"}

    def test_success_true_si_returncode_zero(self):
        result = CommandExecutor.format_result("smartctl", self._proc(returncode=0))
        assert result["success"] is True

    def test_success_false_si_returncode_non_zero(self):
        result = CommandExecutor.format_result("smartctl", self._proc(returncode=1))
        assert result["success"] is False

    def test_stdout_strippe_et_stocke_en_texte_brut(self):
        result = CommandExecutor.format_result("smartctl", self._proc(stdout="  hello\n"))
        assert result["stdout"] == "hello"

    def test_stdout_tronque_a_2000_caracteres(self):
        stdout = "x" * (_STDOUT_LIMIT + 500)
        result = CommandExecutor.format_result("smartctl", self._proc(stdout=stdout))
        assert len(result["stdout"]) == _STDOUT_LIMIT

    def test_stderr_tronque_a_500_caracteres(self):
        stderr = "e" * (_STDERR_LIMIT + 500)
        result = CommandExecutor.format_result("smartctl", self._proc(stderr=stderr))
        assert len(result["stderr"]) == _STDERR_LIMIT

    def test_stdout_pas_parce_en_json(self):
        """Caractérise le défaut actuel : la sortie reste du texte brut,
        même si elle ressemble à du JSON (refacto Phase 4)."""
        result = CommandExecutor.format_result("smartctl", self._proc(stdout='{"a": 1}'))
        assert result["stdout"] == '{"a": 1}'
        assert isinstance(result["stdout"], str)


class TestCommandExecutorRun:
    """Caractérise `CommandExecutor.run` (court-circuits et exécution)."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.executor = _make_executor(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_sans_consentement_court_circuite(self):
        result = self.executor.run("smartctl", consent_given=False)
        assert result == {"success": False, "tool": "smartctl", "error": "Consentement non donné"}

    def test_run_outil_inconnu(self):
        result = self.executor.run("nope", consent_given=True)
        assert not result["success"]
        assert "inconnu" in result["error"]

    def test_run_binaire_introuvable(self):
        result = self.executor.run("smartctl", consent_given=True)
        assert not result["success"]
        assert "introuvable" in result["error"]

    def test_run_success_normalise_le_subprocess(self):
        subdir = _platform_subdir()
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        bin_path = os.path.join(self.tmpdir, "bin", subdir, bin_name)
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        with open(bin_path, "wb") as f:
            f.write(b"fake")
        # sha256 vide pour isoler le comportement d'exécution (cf. tests existants)
        cfg = {"tools": {name: dict(c) for name, c in SAMPLE_CONFIG["tools"].items()}}
        cfg["tools"]["smartctl"]["sha256"] = ""
        self.executor = CommandExecutor(
            config=cfg,
            bin_dir=os.path.join(self.tmpdir, "bin"),
            log_service=FakeLog(),
            verified=set(),
        )
        fake_result = subprocess.CompletedProcess(
            args=[bin_path], returncode=0, stdout="ok output\n", stderr="",
        )
        with mock.patch(
            "services.diagnostic_ext.executor.subprocess.run", return_value=fake_result
        ) as mocked_run:
            result = self.executor.run("smartctl", consent_given=True)

        assert result["success"] is True
        assert result["stdout"] == "ok output"
        assert result["tool"] == "smartctl"
        mocked_run.assert_called_once()


class TestBuildArgs:
    """Caractérise `CommandExecutor.build_args` (plateforme + whitelist)."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.executor = _make_executor(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_args_platform_win32_utilise_cle_args(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        with mock.patch("services.diagnostic_ext.executor.sys.platform", "win32"):
            args = self.executor.build_args(cfg, None, None)
        assert args == ["-a", "{device}"]

    def test_args_platform_linux_utilise_cle_linux_args(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        with mock.patch("services.diagnostic_ext.executor.sys.platform", "linux"):
            args = self.executor.build_args(cfg, None, None)
        assert args == ["-a", "{device}"]

    def test_substitution_cle_dans_whitelist(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        args = self.executor.build_args(cfg, None, {"device": "physicaldrive0"})
        assert args == ["-a", "physicaldrive0"]

    def test_cle_hors_whitelist_ignoree(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        args = self.executor.build_args(cfg, None, {"device": "x", "injected": "evil"})
        assert args == ["-a", "x"]

    def test_valeur_invalide_rejetee(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        args = self.executor.build_args(cfg, None, {"device": "a; rm -rf /"})
        assert args == ["-a", "{device}"]

    def test_cle_port_utilise_port_args_witr(self):
        """W1 — une requête port (clé 'port') bascule sur le template port_args."""
        cfg = {
            "binary": "witr.exe",
            "args": ["--json", "{target}"],
            "port_args": ["--json", "--port", "{port}"],
            "allowed_params": ["target", "port"],
            "sha256": "",
        }
        args = self.executor.build_args(cfg, None, {"port": "8080"})
        assert args == ["--json", "--port", "8080"]


class TestResolveBinary:
    """Caractérise `resolve_binary` (contrat actuel : bin_dir flat)."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_darwin_resout_dans_sous_dossier_darwin(self):
        darwin_dir = os.path.join(self.bin_dir, "darwin")
        os.makedirs(darwin_dir, exist_ok=True)
        bin_path = os.path.join(darwin_dir, "smartctl")
        with open(bin_path, "wb") as f:
            f.write(b"fake")
        with mock.patch("services.diagnostic_ext.binary.sys.platform", "darwin"), mock.patch(
            "services.diagnostic_ext.binary.shutil.which", return_value=None
        ):
            resolved = resolve_binary(SAMPLE_CONFIG, "smartctl", self.bin_dir)
        assert resolved == os.path.abspath(bin_path)

    def test_outil_inconnu_retourne_none(self):
        assert resolve_binary(SAMPLE_CONFIG, "ghost", self.bin_dir) is None

    def test_win32_resout_dans_sous_dossier_win(self):
        win_dir = os.path.join(self.bin_dir, "win")
        os.makedirs(win_dir, exist_ok=True)
        bin_path = os.path.join(win_dir, "smartctl.exe")
        with open(bin_path, "wb") as f:
            f.write(b"fake")
        with mock.patch("services.diagnostic_ext.binary.sys.platform", "win32"):
            resolved = resolve_binary(SAMPLE_CONFIG, "smartctl", self.bin_dir)
        assert resolved == os.path.abspath(bin_path)

    def test_win32_retourne_none_si_binaire_absent(self):
        with mock.patch("services.diagnostic_ext.binary.sys.platform", "win32"):
            resolved = resolve_binary(SAMPLE_CONFIG, "smartctl", self.bin_dir)
        assert resolved is None

    def test_linux_priorite_path_systeme(self):
        # Fichier réel : os.path.isfile doit passer (comportement actuel)
        path_file = os.path.join(self.tmpdir, "usr-bin-smartctl")
        with open(path_file, "wb") as f:
            f.write(b"fake")
        with mock.patch("services.diagnostic_ext.binary.sys.platform", "linux"), mock.patch(
            "services.diagnostic_ext.binary.shutil.which",
            return_value=path_file,
        ):
            resolved = resolve_binary(SAMPLE_CONFIG, "smartctl", self.bin_dir)
        assert resolved == os.path.abspath(path_file)

    def test_linux_repli_sur_sous_dossier_linux(self):
        linux_dir = os.path.join(self.bin_dir, "linux")
        os.makedirs(linux_dir, exist_ok=True)
        bin_path = os.path.join(linux_dir, "smartctl")
        with open(bin_path, "wb") as f:
            f.write(b"fake")
        with mock.patch("services.diagnostic_ext.binary.sys.platform", "linux"), mock.patch(
            "services.diagnostic_ext.binary.shutil.which", return_value=None
        ):
            resolved = resolve_binary(SAMPLE_CONFIG, "smartctl", self.bin_dir)
        assert resolved == os.path.abspath(bin_path)


class TestJsonResultFormatter:
    """Caractérise `JsonResultFormatter` (nouveau contrat Phase 4)."""

    # Extraits réels witr (leçon T5) : en cas de cible ambiguë (ex: svchost),
    # witr bascule en mode interactif — texte brut, liste numérotée [1]..[n],
    # pas de JSON.
    WITR_AMBIGUOUS_STDOUT = (
        "[1] svchost.exe (PID 1416)\n"
        "[2] svchost.exe (PID 1932)\n"
        "[3] svchost.exe (PID 2408)\n"
    )

    def _proc(self, stdout="{}", returncode=0):
        return subprocess.CompletedProcess(
            args=["witr"], returncode=returncode, stdout=stdout, stderr=""
        )

    def test_json_valide_parce_en_data_non_tronque(self):
        big = '{"items": [' + ",".join(f'{{"id": {i}}}' for i in range(3000)) + "]}"
        formatter = JsonResultFormatter()
        result = formatter.format("witr", self._proc(stdout=big))
        assert result["success"] is True
        assert result["tool"] == "witr"
        assert result["returncode"] == 0
        # La structure JSON n'est PAS tronquée : 3000 items préservés
        assert len(result["data"]["items"]) == 3000
        assert "stdout" not in result

    def test_json_valide_returncode_non_zero(self):
        formatter = JsonResultFormatter()
        result = formatter.format("witr", self._proc(stdout='{"ok": false}', returncode=1))
        assert result["success"] is False
        assert result["data"] == {"ok": False}

    def test_json_invalide_retourne_erreur_lisible(self):
        formatter = JsonResultFormatter()
        result = formatter.format("witr", self._proc(stdout="{not valid json"))
        assert result["success"] is False
        assert "JSON invalide" in result["error"]
        assert result["returncode"] == 0

    def test_json_vide_retourne_erreur(self):
        formatter = JsonResultFormatter()
        result = formatter.format("witr", self._proc(stdout=""))
        assert result["success"] is False
        assert "JSON invalide" in result["error"]

    def test_mode_interactif_liste_numerotee_distinguce_d_erreur_json(self):
        """Plusieurs process matchent (ex: svchost) → witr sort une liste
        numérotée en texte brut. Le formatter doit caractériser ce cas
        (cible ambiguë), pas le confondre avec un JSON invalide."""
        formatter = JsonResultFormatter()
        result = formatter.format(
            "witr", self._proc(stdout=self.WITR_AMBIGUOUS_STDOUT, returncode=0)
        )
        assert result["success"] is False
        assert "ambig" in result["error"].lower()
        assert "JSON invalide" not in result["error"]
        assert result["data"]["ambiguous"] is True
        assert len(result["data"]["candidates"]) == 3

    def test_get_formatter_json(self):
        assert isinstance(get_formatter("json"), JsonResultFormatter)

    def test_get_formatter_text_defaut(self):
        assert isinstance(get_formatter("text"), TextResultFormatter)
        assert isinstance(get_formatter("inconnu"), TextResultFormatter)
        assert isinstance(get_formatter(""), TextResultFormatter)

    def test_executor_run_avec_output_format_json(self):
        """run() sélectionne le JsonResultFormatter quand output_format=json."""
        tmpdir = tempfile.mkdtemp()
        try:
            cfg = {
                "tools": {
                    "witr": {
                        "binary": "witr.exe",
                        "linux_binary": "witr",
                        "darwin_binary": "witr",
                        "timeout": 5,
                        "output_format": "json",
                        "args": ["--json", "{target}"],
                        "allowed_params": ["target"],
                        "sha256": "",
                    }
                }
            }
            executor = _make_executor(tmpdir, config=cfg)
            subdir = _platform_subdir()
            bin_name = "witr.exe" if sys.platform == "win32" else "witr"
            bin_path = os.path.join(tmpdir, "bin", subdir, bin_name)
            os.makedirs(os.path.dirname(bin_path), exist_ok=True)
            with open(bin_path, "wb") as f:
                f.write(b"fake")
            fake_result = subprocess.CompletedProcess(
                args=[bin_path], returncode=0, stdout='{"process": "nginx"}', stderr="",
            )
            with mock.patch(
                "services.diagnostic_ext.executor.subprocess.run", return_value=fake_result
            ):
                result = executor.run("witr", consent_given=True, extra_kwargs={"target": "nginx"})
            assert result["success"] is True
            assert result["data"] == {"process": "nginx"}
            assert "stdout" not in result
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRunWitr:
    """Caractérise `DiagnosticExtService.run_witr` (convention run_xxx)."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "tools.yaml")
        with open(self.config_path, "w") as f:
            yaml.dump(SAMPLE_CONFIG, f)
        self.bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.consent_file = os.path.join(self.tmpdir, ".consent")
        self.log = FakeLog()
        self.svc = DiagnosticExtService(
            config_path=self.config_path,
            bin_dir=self.bin_dir,
            consent_file=self.consent_file,
            log_service=self.log,
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_witr_delegue_a_run_tool_avec_target(self):
        with mock.patch.object(
            self.svc, "_run_tool", return_value={"success": True, "tool": "witr"}
        ) as mocked:
            result = self.svc.run_witr("nginx")
        mocked.assert_called_once_with("witr", extra_kwargs={"target": "nginx"})
        assert result == {"success": True, "tool": "witr"}

    def test_run_witr_passe_le_target_port(self):
        """W1 — un target purement numérique est traité comme un port (clé 'port')."""
        with mock.patch.object(self.svc, "_run_tool", return_value={}) as mocked:
            self.svc.run_witr("8080")
        mocked.assert_called_once_with("witr", extra_kwargs={"port": "8080"})

    def test_run_witr_sans_consentement_court_circuite(self):
        result = self.svc.run_witr("nginx")
        assert not result["success"]
        assert "Consentement" in result["error"]

    def test_run_witr_cible_ambigue_remonte_data_ambiguous(self):
        """Sortie witr en liste numérotée (plusieurs process matchent) →
        `data.ambiguous: True` + `candidates` peuplé, remonté proprement."""
        subdir = _platform_subdir()
        bin_name = "witr.exe" if sys.platform == "win32" else "witr"
        bin_path = os.path.join(self.bin_dir, subdir, bin_name)
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        with open(bin_path, "wb") as f:
            f.write(b"fake")
        cfg = {
            "tools": {
                "witr": {
                    "binary": "witr.exe",
                    "linux_binary": "witr",
                    "darwin_binary": "witr",
                    "timeout": 5,
                    "output_format": "json",
                    "args": ["--json", "{target}"],
                    "allowed_params": ["target"],
                    "sha256": "",
                }
            }
        }
        with open(self.config_path, "w") as f:
            yaml.dump(cfg, f)
        svc = DiagnosticExtService(
            config_path=self.config_path,
            bin_dir=self.bin_dir,
            consent_file=self.consent_file,
            log_service=self.log,
        )
        svc.grant_consent()
        fake_result = subprocess.CompletedProcess(
            args=[bin_path],
            returncode=0,
            stdout=TestJsonResultFormatter.WITR_AMBIGUOUS_STDOUT,
            stderr="",
        )
        with mock.patch(
            "services.diagnostic_ext.executor.subprocess.run", return_value=fake_result
        ):
            result = svc.run_witr("svchost")
        assert result["success"] is False
        assert result["data"]["ambiguous"] is True
        assert len(result["data"]["candidates"]) == 3
        assert "ambig" in result["error"].lower()


class TestServiceCheckTools:
    """Caractérise `check_all_tools` / `list_available` / `is_ready`."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "tools.yaml")
        with open(self.config_path, "w") as f:
            yaml.dump(SAMPLE_CONFIG, f)
        self.bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.consent_file = os.path.join(self.tmpdir, ".consent")
        self.log = FakeLog()
        self.svc = DiagnosticExtService(
            config_path=self.config_path,
            bin_dir=self.bin_dir,
            consent_file=self.consent_file,
            log_service=self.log,
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_all_tools_retourne_structure_par_outil(self):
        results = self.svc.check_all_tools()
        assert set(results) == {"smartctl", "psinfo"}
        for info in results.values():
            assert set(info) == {"available", "path", "sha256_ok", "platforms"}

    def test_check_all_tools_sans_binaires_aucun_disponible(self):
        results = self.svc.check_all_tools()
        assert all(not info["available"] for info in results.values())

    def test_list_available_vide_sans_binaire(self):
        assert self.svc.list_available() == []

    def test_list_available_exige_sha256_ok(self):
        subdir = _platform_subdir()
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        bin_path = os.path.join(self.bin_dir, subdir, bin_name)
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        with open(bin_path, "wb") as f:
            f.write(b"\x00" * 100)
        # Binaire présent mais SHA256 faux (contenu fake) → PAS dans la liste
        assert self.svc.list_available() == []

    def test_is_ready_false_sans_consentement(self):
        assert not self.svc.is_ready()

    def test_is_ready_false_sans_outil_disponible(self):
        self.svc.grant_consent()
        assert not self.svc.is_ready()

    def test_check_tool_witr_linux_utilise_hash_linux(self):
        """Sous linux, le hash attendu est `linux_sha256`, pas le hash win32.

        Patch global `sys.platform` : couvre binary.py (resolve_binary) ET
        service.py (resolve du hash attendu) en un seul point.
        """
        linux_dir = os.path.join(self.bin_dir, "linux")
        os.makedirs(linux_dir, exist_ok=True)
        bin_path = os.path.join(linux_dir, "witr")
        content = b"linux-witr-binary"
        with open(bin_path, "wb") as f:
            f.write(content)
        cfg = {
            "tools": {
                "witr": {
                    "binary": "witr.exe",
                    "linux_binary": "witr",
                    "timeout": 5,
                    "platforms": ["win32", "linux"],
                    "args": ["--json", "{target}"],
                    "allowed_params": ["target"],
                    "sha256": "A" * 64,
                    "linux_sha256": hashlib.sha256(content).hexdigest().upper(),
                }
            }
        }
        with open(self.config_path, "w") as f:
            yaml.dump(cfg, f)
        svc = DiagnosticExtService(
            config_path=self.config_path,
            bin_dir=self.bin_dir,
            consent_file=self.consent_file,
            log_service=self.log,
        )
        with mock.patch("sys.platform", "linux"), mock.patch(
            "services.diagnostic_ext.binary.shutil.which", return_value=None
        ):
            result = svc._check_tool("witr")
        assert result["available"] is True
        assert result["sha256_ok"] is True


__all__ = [
    "SAMPLE_CONFIG",
    "FakeLog",
    "_make_executor",
    "TestFormatResult",
    "TestCommandExecutorRun",
    "TestBuildArgs",
    "TestResolveBinary",
    "TestServiceCheckTools",
]
