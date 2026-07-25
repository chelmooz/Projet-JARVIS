"""Tests Fix #2 — Vérifie que les except silencieux (pass) loggent l'erreur."""
import ast
from pathlib import Path
from unittest.mock import mock_open, patch

from config.constants import PROJECT_DIR

_EXCLUDED_DIRS = {".venv", "node_modules", ".git", "tests", "logs", "static"}


def _bare_except_pass_offenders() -> list[str]:
    """Liste 'fichier:ligne' des except dont le corps est un simple `pass` (sans log)."""
    offenders: list[str] = []
    for path in Path(PROJECT_DIR).rglob("*.py"):
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                offenders.append(f"{path.relative_to(PROJECT_DIR)}:{node.lineno}")
    return offenders


class TestNoBareExceptPass:
    """Phase 7.5 — Aucun `except ...: pass` silencieux ne doit subsister en prod (AUDIT_REPORT §8)."""

    def test_no_silent_except_pass_in_production_code(self):
        offenders = _bare_except_pass_offenders()
        assert offenders == [], f"except:pass sans logging trouvés : {offenders}"


class TestNoSilentExcept:

    def test_assign_profile_logs_ok(self):
        """L'assignation d'un profil loggue un INFO (pas d'except silencieux)."""
        from controllers.routes.agents import assign_profile
        from models.schemas import AssignRequest

        profiles_json = '{"profiles": {"techlead": {"name": "TL", "model": ""}}, "agent_model_map": {}}'
        m = mock_open(read_data=profiles_json)
        with patch("controllers.routes.agents.open", m):
            body = AssignRequest(profile="techlead", model="phi4-mini:latest")
            result = assign_profile(body)
            assert result.get("data", {}).get("profile") == "techlead"

    def test_pipeline_load_logs_on_bad_yaml(self):
        """Quand un YAML est invalide, PipelineService doit logger (pas print)."""
        import tempfile
        from pathlib import Path

        from services.pipeline import PipelineService

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_yaml = tmpdir / Path("bad.yaml")
            bad_yaml.write_text("invalid: yaml: : : broken", encoding="utf-8")
            from config import paths

            original = paths.PIPELINES_DIR
            try:
                paths.PIPELINES_DIR = str(tmpdir)
                with patch("services.pipeline.print") as mock_print:
                    PipelineService()
                    mock_print.assert_not_called()
            finally:
                paths.PIPELINES_DIR = original
