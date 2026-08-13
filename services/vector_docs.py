"""Construction des documents de l'index vectoriel — formatage pur.

Extraites de ``VectorService`` (découpage Phase 20) : la construction
du document standardisé d'un message de conversation est une fonction
pure, indépendante de l'état de l'index.
"""

from __future__ import annotations

from typing import Any


def build_message_doc(
    conv_id: str, msg_id: str, role: str, content: str, ts: float, extra: dict[str, Any] | None
) -> dict[str, Any]:
    """Construit un document de message standardisé."""
    return {
        "text": content,
        "metadata": {
            "source": "conversation",
            "conv_id": conv_id,
            "msg_id": msg_id,
            "role": role,
            "created_at": ts,
            "weight": 1.0,
            **(extra or {}),
        },
        "embedding": None,
    }
