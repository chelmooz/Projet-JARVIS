"""Routes Documents — Ingestion, vectorisation, recherche.

Dettes signalées (non corrigées ici) :
- Les payloads d'erreur de ``ingest_documents`` et ``search_documents``
  retournent des structures ad hoc (``{error, ingested}``, ``{error, results}``)
  au lieu de la convention ``{data, error}`` : le frontend attend ces formes
  plates. À trancher avec le contrat frontend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from controllers.context import get_app_context, _ctx
from controllers.di import AppContext
from controllers.responses import ok
from models.schemas import IngestRequest
from services.sanitize import scrub
from services.vector import EXPECTED_MODEL

_logger = logging.getLogger(__name__)

router = APIRouter()

# Exposition au niveau module
_ctx = _ctx  # Rend le symbole explicitement accessible via documents._ctx
BATCH_SIZE = 5
SEARCH_MAX_LIMIT = 100


def _vectorize_one_conversation(context: AppContext, conv_id: str) -> tuple[int, str | None]:
    """Vectorise une conversation et la marque indexée (non destructive).

    Retourne ``(nombre de documents indexés, erreur | None)``.
    Aucun ``None`` silencieux : l'erreur est toujours une chaîne explicite ou ``None``.
    La conversation source est conservée ; seul un marqueur ``indexed`` évite le retraitement infini.
    """
    conv = context.conversations.get_conversation(conv_id)
    if not conv or "messages" not in conv:
        return 0, "Conversation introuvable"

    texts = [msg.get("content", "").strip() for msg in conv["messages"]]
    texts = [text for text in texts if text]
    if not texts:
        context.conversations.mark_indexed(conv_id)
        return 0, None

    pairs = [(text, {"source": "conversation", "conv_id": conv_id}) for text in texts]
    context.vector.index_batch(pairs)
    context.vector.vectorize_pending()
    context.conversations.mark_indexed(conv_id)
    context.analytics.track_query(agent="vectorize", model=EXPECTED_MODEL, success=True)
    return len(texts), None


@router.post("/api/vectorize/conversations")
def vectorize_conversations(context: AppContext = Depends(get_app_context)):
    """Vectorise les conversations non indexées, par batch, sans les supprimer.

    Lit les conversations non indexées depuis l'index, indexe chaque message
    dans le store vectoriel, déclenche l'embedding, puis marque chaque
    conversation comme indexée (idempotent : ne retraite jamais deux fois).
    Limite : ``BATCH_SIZE`` = 5 conversations par appel.
    """
    unindexed = context.conversations.list_unindexed()
    batch = unindexed[:BATCH_SIZE]
    if not batch:
        return ok({"vectorized": 0, "conversations": 0, "message": "Aucune conversation à traiter"})

    total_docs = 0
    treated = 0
    errors = []

    for entry in batch:
        try:
            docs, error = _vectorize_one_conversation(context, entry["id"])
        except Exception as e:  # noqa: BLE001 - défensif
            errors.append({"id": entry["id"], "error": str(e)})
            continue
        if error:
            errors.append({"id": entry["id"], "error": error})
            continue
        treated += 1
        total_docs += docs

    stats = context.vector.stats()
    remaining = len(unindexed) - treated
    context.log.log("INFO", f"Vectorisation conversations: {treated} traitées, {total_docs} docs, {remaining} restantes")
    return ok({
        "vectorized": total_docs,
        "conversations": treated,
        "remaining": remaining,
        "errors": errors,
        **stats,
    })


@router.post("/api/ingest")
def ingest_documents(body: IngestRequest, context: AppContext = Depends(get_app_context)):
    """Ingeste des documents bruts dans le store vectoriel."""
    if not body.documents:
        return JSONResponse({"error": "Liste 'documents' vide", "ingested": 0}, status_code=400)
    pairs = []
    for doc in body.documents:
        if doc.text:
            metadata = doc.metadata or {}
            metadata["source"] = body.source
            pairs.append((doc.text, metadata))
    context.vector.index_batch(pairs)
    context.log.log("INFO", "Ingested %d documents from '%s'", len(pairs), body.source)
    return ok({"ingested": len(pairs)})


@router.post("/api/vectorize")
def vectorize_pending(context: AppContext = Depends(get_app_context)):
    """Force la vectorisation des documents en attente (pending)."""
    count = context.vector.vectorize_pending()
    stats = context.vector.stats()
    context.log.log("INFO", "Vectorisation: %d documents traités", count)
    return ok({"vectorized": count, **stats})


@router.get("/api/vectorize")
async def vectorize_stats(context: AppContext = Depends(get_app_context)):
    """Statistiques du store vectoriel (compteurs en mémoire, safe en async)."""
    return context.vector.stats()


@router.get("/api/search")
def search_documents(
    q: str = "",
    top_k: int = 20,
    limit: int = 20,
    offset: int = 0,
    context: AppContext = Depends(get_app_context),
):
    """Recherche sémantique dans le store vectoriel.

    Laisse sync : recherche vectorielle CPU-bound (bloquerait la boucle d'événements en async).
    """
    if not q.strip():
        return JSONResponse({"error": "Paramètre 'q' requis", "results": []}, status_code=400)
    # Bornes de pagination : limite plafonnée à 100, offset et limite >= 0.
    limit = min(max(int(limit), 0), SEARCH_MAX_LIMIT)
    offset = max(int(offset), 0)
    # Récupère assez de résultats pour couvrir la page demandée (troncature en Python).
    results = context.vector.search(q, top_k=offset + limit)
    total = len(results)
    page = results[offset:offset + limit]
    # Scrub PII sur les textes renvoyés (emails, IPs, credentials) — jamais en clair.
    for r in page:
        if isinstance(r, dict) and "text" in r:
            r["text"] = scrub(r["text"])
    return ok({
        "query": q,
        "results": page,
        "total": total,
        "count": len(page),
        "limit": limit,
        "offset": offset,
    })


__all__ = ["router"]
