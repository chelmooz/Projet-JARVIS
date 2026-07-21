"""Routes Conversations — CRUD conversations."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.constants import FEEDBACK_WEIGHTS
from controllers.context import get_app_context
from controllers.di import AppContext
from controllers.responses import fail, ok

_logger = logging.getLogger(__name__)

router = APIRouter()

# Borne maximale pour la pagination (évite les réponses déraisonnables).
CONV_MAX_LIMIT = 100


class CreateConvRequest(BaseModel):
    title: str = ""


class AddMessageRequest(BaseModel):
    role: str = "user"
    content: str = ""


class FeedbackRequest(BaseModel):
    conv_id: str
    msg_id: str
    signal: int  # +1 (positif) ou -1 (negatif)


class ImplicitFeedbackRequest(BaseModel):
    conv_id: str
    msg_id: str
    type: str  # copy | edit | revisit | regenerate | delete_conv


@router.post("/api/conversations")
def create_conversation(
    body: CreateConvRequest | None = None,
    context: AppContext = Depends(get_app_context),
):
    title = (body.title if body and body.title else "Nouvelle conversation").strip()
    if not title:
        title = "Nouvelle conversation"
    conv_id = context.conversations.create(title=title)
    return ok({"conversation_id": conv_id, "title": title})


@router.post("/api/conversations/{conv_id}/messages")
def add_message(
    conv_id: str,
    body: AddMessageRequest,
    context: AppContext = Depends(get_app_context),
):
    if not conv_id.strip():
        return fail("conversation_id invalide", status_code=400)
    try:
        context.conversations.add_message(conv_id, body.role, body.content)
        return ok({"status": "ok"})
    except Exception as e:  # noqa: BLE001 - défensif
        _logger.warning("Échec ajout message conv %s: %s", conv_id, e)
        return fail(str(e), status_code=500)


@router.get("/api/conversations")
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    context: AppContext = Depends(get_app_context),
):
    # list_all() lit l'index en mémoire : safe en async.
    # Bornes de pagination : limite plafonnée à 100, offset et limite >= 0.
    limit = min(max(int(limit), 0), CONV_MAX_LIMIT)
    offset = max(int(offset), 0)
    all_convs = context.conversations.list_all()
    return ok({
        "conversations": all_convs[offset:offset + limit],
        "total": len(all_convs),
        "limit": limit,
        "offset": offset,
    })


@router.get("/api/conversations/{conv_id}")
def get_conversation(
    conv_id: str,
    context: AppContext = Depends(get_app_context),
):
    # Laisse sync : lit un fichier JSON de conversation (I/O bloquant).
    if not conv_id.strip():
        return fail("conversation_id invalide", status_code=400)
    conv = context.conversations.get_conversation(conv_id)
    if conv is None:
        return fail("Conversation introuvable", status_code=404)
    return ok(conv)


@router.delete("/api/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    context: AppContext = Depends(get_app_context),
):
    if not conv_id.strip():
        return fail("conversation_id invalide", status_code=400)
    context.conversations.delete(conv_id)
    return ok({"status": "ok"})


@router.delete("/api/conversations")
def delete_all_conversations(context: AppContext = Depends(get_app_context)):
    context.conversations.delete_all()
    return ok({"status": "ok"})


@router.post("/api/feedback")
def post_feedback(
    body: FeedbackRequest,
    context: AppContext = Depends(get_app_context),
):
    """Feedback explicite (👍/) sur un message : ajuste le poids du souvenir."""
    if not body.conv_id.strip() or not body.msg_id.strip():
        return fail("conv_id/msg_id invalide", status_code=400)
    delta = 1.0 if body.signal > 0 else (-1.0 if body.signal < 0 else 0.0)
    if delta == 0:
        return fail("signal doit être +1 ou -1", status_code=400)
    count = context.vector.adjust_weight(
        body.conv_id, body.msg_id, delta, conversations=context.conversations,
    )
    return ok({"status": "ok", "adjusted": count, **context.vector.stats()})


@router.post("/api/feedback/implicit")
def post_feedback_implicit(
    body: ImplicitFeedbackRequest,
    context: AppContext = Depends(get_app_context),
):
    """Feedback implicite (copie/edition/relecture/regeneration/suppression)."""
    if not body.conv_id.strip() or not body.msg_id.strip():
        return fail("conv_id/msg_id invalide", status_code=400)
    delta = FEEDBACK_WEIGHTS.get(body.type)
    if delta is None:
        return fail(f"type inconnu: {body.type}", status_code=400)
    count = context.vector.adjust_weight(
        body.conv_id, body.msg_id, delta, conversations=context.conversations,
    )
    return ok({
        "status": "ok", "type": body.type, "delta": delta,
        "adjusted": count, **context.vector.stats(),
    })


__all__ = ["router"]
