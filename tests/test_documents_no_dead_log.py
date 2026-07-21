"""Tests Fix #1 — Vérifie que log.log() n'est plus appelé (dead code → AttributeError)."""
from unittest.mock import MagicMock, patch

# Assure que le contexte applicatif (singletons log/vector/...) est initialise,
# comme lors d'un demarrage reel de l'API (build_app avant l'import des routes).
from controllers.context import build_app

build_app()
import controllers.router  # noqa: E402,F401


class TestDocumentsNoDeadLog:

    @patch("controllers.context.vector")
    def test_ingest_no_log_dot_log_crash(self, mock_vector):
        """Vérifie que ingest_documents ne lève pas AttributeError sur log.log()."""
        mock_vector.index_batch = MagicMock()
        from controllers.routes.documents import ingest_documents
        from models.schemas import IngestDocument, IngestRequest

        body = IngestRequest(
            documents=[IngestDocument(text="hello", metadata={"type": "test"})],
            source="test",
        )
        result = ingest_documents(body)
        assert result["status"] == "ok"
        assert result["ingested"] == 1

    @patch("controllers.context.vector")
    def test_vectorize_no_log_dot_log_crash(self, mock_vector):
        """Vérifie que vectorize_pending ne lève pas AttributeError sur log.log()."""
        mock_vector.vectorize_pending.return_value = 0
        mock_vector.stats.return_value = {"total": 0}
        from controllers.routes.documents import vectorize_pending

        result = vectorize_pending()
        assert result["status"] == "ok"

    @patch("controllers.routes.agents.inference")
    @patch("controllers.routes.agents.memory")
    @patch("controllers.routes.agents.analytics")
    def test_assign_profile_no_log_dot_log_crash(
        self, mock_analytics, mock_memory, mock_inference
    ):
        """Vérifie que assign_profile ne lève pas AttributeError sur log.log()."""
        mock_inference.select_backend = MagicMock()
        from controllers.routes.agents import assign_profile
        from models.schemas import AssignRequest

        with patch(
            "controllers.routes.agents.open",
            new_callable=MagicMock,
        ) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = (
                '{"profiles": {"techlead": {"name": "TL", "model": ""}}, "agent_model_map": {}}'
            )
            mock_open().__enter__.return_value = mock_file.__enter__.return_value
            body = AssignRequest(profile="techlead", model="phi4-mini:latest")
            result = assign_profile(body)
            assert result["status"] == "ok"
