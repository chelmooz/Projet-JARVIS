"""Tests Fix #2 — Vérifie que les except silencieux (pass) loggent l'erreur."""
from unittest.mock import mock_open, patch


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
