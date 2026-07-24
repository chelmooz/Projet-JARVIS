"""Tests Fix #1 — Vérifie que log.log() n'est plus appelé (dead code → AttributeError)."""
from unittest.mock import MagicMock, patch

# Assure que le contexte applicatif (singletons log/vector/...) est initialise,
# comme lors d'un demarrage reel de l'API (build_app avant l'import des routes).
from controllers.context import build_app

build_app()
import controllers.router  # noqa: E402,F401


def _mock_context():
    """Crée un AppContext factice pour les appels directs aux routes."""
    from controllers.di import AppContext
    ctx = AppContext()
    ctx.vector = MagicMock()
    ctx.vector.index_batch = MagicMock()
    ctx.vector.vectorize_pending.return_value = 0
    ctx.vector.stats.return_value = {"total": 0}
    ctx.log = MagicMock()
    return ctx


class TestDocumentsNoDeadLog:

    def test_ingest_no_log_dot_log_crash(self):
        """Vérifie que ingest_documents ne lève pas AttributeError sur log.log()."""
        from controllers.routes.documents import ingest_documents
        from models.schemas import IngestDocument, IngestRequest

        ctx = _mock_context()
        body = IngestRequest(
            documents=[IngestDocument(text="hello", metadata={"type": "test"})],
            source="test",
        )
        result = ingest_documents(body, ctx)
        assert result["data"]["ingested"] == 1

    def test_vectorize_no_log_dot_log_crash(self):
        """Vérifie que vectorize_pending ne lève pas AttributeError sur log.log()."""
        from controllers.routes.documents import vectorize_pending

        ctx = _mock_context()
        result = vectorize_pending(ctx)
        assert "vectorized" in result.get("data", {})

    def test_assign_profile_no_log_dot_log_crash(self):
        """Vérifie que assign_profile ne lève pas AttributeError sur log.log()."""
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
            assert result.get("data", {}).get("profile") == "techlead"
