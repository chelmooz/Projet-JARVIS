"""Tests de sécurité — Fuite de détails d'erreur internes vers le client.

Contexte : `vectorize_conversations` (controllers/routes/documents.py) capture
toute exception levée pendant le traitement d'une conversation et renvoie
`str(e)` telle quelle dans la réponse JSON (`errors: [{"id":..., "error": ...}]`).
Si l'exception contient un détail interne (chemin, requête SQL, credential...),
il part directement au client. On veut un message générique côté client,
et le détail réel loggé côté serveur (`exc_info=True`).
"""
from unittest.mock import MagicMock, patch

from controllers.context import build_app

build_app()
import controllers.router  # noqa: E402,F401


def _mock_context_with_failing_conversation(sensitive_message: str):
    from controllers.di import AppContext

    ctx = AppContext()
    ctx.conversations = MagicMock()
    ctx.conversations.list_unindexed.return_value = [{"id": "conv-1"}]
    ctx.conversations.get_conversation.side_effect = RuntimeError(sensitive_message)
    ctx.vector = MagicMock()
    ctx.vector.stats.return_value = {"total": 0}
    ctx.log = MagicMock()
    return ctx


class TestVectorizeConversationsErrorLeakage:

    def test_internal_exception_message_not_leaked_to_client(self):
        """Le détail brut de l'exception ne doit jamais apparaître dans la réponse JSON."""
        from controllers.routes.documents import vectorize_conversations

        sensitive_message = "sqlite3.OperationalError: /home/user/.jarvis/secret_store.db is locked"
        ctx = _mock_context_with_failing_conversation(sensitive_message)

        result = vectorize_conversations(ctx)

        errors = result["data"]["errors"]
        assert len(errors) == 1
        assert sensitive_message not in errors[0]["error"], (
            "Le message d'exception brut ne doit pas être renvoyé au client "
            f"(reçu : {errors[0]['error']!r})"
        )

    def test_internal_exception_is_logged_with_traceback(self):
        """L'exception réelle doit être loggée côté serveur (exc_info=True), pas perdue."""
        from controllers.routes.documents import vectorize_conversations

        sensitive_message = "sqlite3.OperationalError: /home/user/.jarvis/secret_store.db is locked"
        ctx = _mock_context_with_failing_conversation(sensitive_message)

        with patch("controllers.routes.documents._logger") as mock_logger:
            vectorize_conversations(ctx)
            assert mock_logger.error.called, "L'exception doit être loggée via _logger.error(...)"
            _, kwargs = mock_logger.error.call_args
            assert kwargs.get("exc_info") is True, (
                "Le log doit inclure exc_info=True pour garder la trace complète côté serveur"
            )
