"""Routes Documents — Ingestion, vectorisation, recherche.

Dettes signalées (non corrigées ici) :
- Les payloads d'erreur de ``ingest_documents`` et ``search_documents``
  retournent des structures ad hoc (``{error, ingested}``, ``{error, results}``)
  au lieu de la convention ``{data, error}`` : le frontend attend ces formes
  plates. À trancher avec le contrat frontend.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from config.constants import CHUNK_OVERLAP, CHUNK_SIZE
from controllers.context import get_app_context
from controllers.di import AppContext
from controllers.responses import Envelope, ok
from models.schemas import IngestRequest
from services.chunker import chunk_text
from services.sanitize import scrub
from services.vector import EXPECTED_MODEL

_logger = logging.getLogger(__name__)

router = APIRouter()

BATCH_SIZE = 5
SEARCH_MAX_LIMIT = 100


def _vectorize_conversations_batch(context: AppContext, conv_ids: list[str]) -> tuple[int, list[dict[str, Any]]]:
    """Vectorise plusieurs conversations en un batch unique.

    Retourne ``(total documents indexés, liste d'erreurs)``.
    """
    assert context.conversations is not None
    assert context.vector is not None
    all_pairs: list[tuple[str, dict[str, Any] | None]] = []
    errors: list[dict[str, Any]] = []

    for conv_id in conv_ids:
        try:
            conv = context.conversations.get_conversation(conv_id)
        except Exception as e:
            _logger.error("Échec récupération conversation %s: %s", conv_id, e, exc_info=True)
            errors.append({"id": conv_id, "error": "Erreur interne lors de la vectorisation"})
            continue

        if not conv or "messages" not in conv:
            errors.append({"id": conv_id, "error": "Conversation introuvable"})
            continue

        texts = [str(msg.get("content", "")).strip() for msg in conv["messages"]]
        texts = [text for text in texts if text]
        if not texts:
            context.conversations.mark_indexed(conv_id)
            continue

        pairs = [(text, {"source": "conversation", "conv_id": conv_id}) for text in texts]
        all_pairs.extend(pairs)

    if not all_pairs:
        return 0, errors

    # UN SEUL batch pour toutes les conversations
    context.vector.index_batch(all_pairs)
    context.vector.vectorize_pending()
    context.vector.flush()

    # Marquer toutes les conversations comme indexées
    for conv_id in conv_ids:
        context.conversations.mark_indexed(conv_id)

    if context.analytics is not None:
        context.analytics.track_query(agent="vectorize", model=EXPECTED_MODEL, success=True)
    return len(all_pairs), errors


@router.post("/api/vectorize/conversations")
def vectorize_conversations(context: AppContext = Depends(get_app_context)) -> Envelope:
    """Vectorise les conversations non indexées, par batch, sans les supprimer.

    Lit les conversations non indexées depuis l'index, indexe chaque message
    dans le store vectoriel, déclenche l'embedding, puis marque chaque
    conversation comme indexée (idempotent : ne retraite jamais deux fois).
    Limite : ``BATCH_SIZE`` = 5 conversations par appel.
    """
    assert context.conversations is not None
    assert context.vector is not None
    assert context.log is not None
    unindexed = context.conversations.list_unindexed()
    batch = unindexed[:BATCH_SIZE]
    if not batch:
        return ok({"vectorized": 0, "conversations": 0, "message": "Aucune conversation à traiter"})

    conv_ids = [entry["id"] for entry in batch]
    total_docs, errors = _vectorize_conversations_batch(context, conv_ids)

    stats = context.vector.stats()
    remaining = len(unindexed) - len(batch)
    context.log.log(
        "INFO", f"Vectorisation conversations: {len(batch)} traitées, {total_docs} docs, {remaining} restantes"
    )
    return ok(
        {
            "vectorized": total_docs,
            "conversations": len(batch),
            "remaining": remaining,
            "errors": errors,
            **stats,
        }
    )


@router.post("/api/ingest")
def ingest_documents(body: IngestRequest, context: AppContext = Depends(get_app_context)) -> Any:
    """Ingeste des documents bruts dans le store vectoriel (chunking sémantique)."""
    assert context.vector is not None
    assert context.log is not None
    if not body.documents:
        return JSONResponse({"error": "Liste 'documents' vide", "ingested": 0}, status_code=400)
    pairs: list[tuple[str, dict[str, Any] | None]] = []
    for doc in body.documents:
        if doc.text:
            base_meta = dict(doc.metadata)
            base_meta["source"] = body.source
            doc_id = base_meta.get("doc_id", "")
            chunks = chunk_text(doc.text, CHUNK_SIZE, CHUNK_OVERLAP, doc_id=doc_id)
            for c in chunks:
                meta = base_meta.copy()
                meta.update(c["metadata"])
                pairs.append((c["text"], meta))
    context.vector.index_batch(pairs)
    context.log.log("INFO", f"Ingested {len(pairs)} chunks from {len(body.documents)} documents ('{body.source}')")
    return ok({"ingested": len(pairs)})


@router.post("/api/vectorize")
def vectorize_pending(context: AppContext = Depends(get_app_context)) -> Envelope:
    """Force la vectorisation des documents en attente (pending)."""
    assert context.vector is not None
    assert context.log is not None
    count = context.vector.vectorize_pending()
    stats = context.vector.stats()
    context.log.log("INFO", f"Vectorisation: {count} documents traités")
    return ok({"vectorized": count, **stats})


@router.get("/api/vectorize")
async def vectorize_stats(context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    """Statistiques du store vectoriel (compteurs en mémoire, safe en async)."""
    assert context.vector is not None
    return context.vector.stats()


@router.get("/api/search")
def search_documents(
    q: str = "",
    limit: int = 20,
    offset: int = 0,
    agent: str = "",
    context: AppContext = Depends(get_app_context),
) -> Any:
    """Recherche sémantique dans le store vectoriel avec pagination et cache.

    Laisse sync : recherche vectorielle CPU-bound (bloquerait la boucle d'événements en async).

    ``agent`` : filtre optionnel sur ``metadata.agent`` (ex: "@cyber").
    La forme sans '@' (ex: "cyber") est normalisée automatiquement.
    """
    assert context.vector is not None
    if not q.strip():
        return JSONResponse({"error": "Paramètre 'q' requis", "results": []}, status_code=400)
    # Bornes de pagination : limite plafonnée à 100, offset et limite >= 0.
    limit = min(max(int(limit), 0), SEARCH_MAX_LIMIT)
    offset = max(int(offset), 0)
    agent_filter = f"@{agent.strip().lstrip('@')}" if agent.strip() else None
    # Recherche une seule fois avec top_k fixe (SEARCH_MAX_LIMIT) pour tirer parti du cache vectoriel.
    # La clé de cache dépend de (query, top_k) — utiliser top_k constant évite les re-recherches par page.
    results = context.vector.search(q, top_k=SEARCH_MAX_LIMIT, agent=agent_filter)
    total = len(results)
    page = results[offset : offset + limit]
    # Scrub PII sur les textes renvoyés (emails, IPs, credentials) — jamais en clair.
    for r in page:
        if isinstance(r, dict) and "text" in r:
            r["text"] = scrub(r["text"])
    return ok(
        {
            "query": q,
            "results": page,
            "total": total,
            "count": len(page),
            "limit": limit,
            "offset": offset,
        }
    )


__all__ = ["router"]
