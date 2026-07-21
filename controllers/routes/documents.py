"""Routes Documents — Ingestion, vectorisation, recherche."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models.schemas import IngestRequest
from services.sanitize import scrub
from services.vector import EXPECTED_MODEL

router = APIRouter()
BATCH_SIZE = 5


def _ctx():
    """Lazy import : les singletons ne sont disponibles qu'apres build_app()."""
    from controllers.context import analytics, conversations, log, vector
    return conversations, log, vector, analytics


@router.post("/api/vectorize/conversations")
def vectorize_conversations():
    """Vectorise les conversations non indexees, par batch, sans les supprimer.

    Lit les conversations non indexees depuis l'index, indexe chaque message
    dans le store vectoriel, declenche l'embedding, puis marque chaque
    conversation comme indexee (idempotent : ne retraite jamais deux fois).
    Limite : BATCH_SIZE = 5 conversations par appel.
    """
    conversations, log, vector, _ = _ctx()
    unindexed = conversations.list_unindexed()
    batch = unindexed[:BATCH_SIZE]
    if not batch:
        return {"status": "ok", "vectorized": 0, "conversations": 0, "message": "Aucune conversation a traiter"}

    total_docs = 0
    treated = 0
    errors = []

    for entry in batch:
        try:
            docs, error = _vectorize_one_conversation(entry["id"])
        except Exception as e:
            errors.append({"id": entry["id"], "error": str(e)})
            continue
        if error:
            errors.append({"id": entry["id"], "error": error})
            continue
        treated += 1
        total_docs += docs

    stats = vector.stats()
    remaining = len(unindexed) - treated
    log.log("INFO", f"Vectorisation conversations: {treated} traitees, {total_docs} docs, {remaining} restantes")
    return {
        "status": "ok",
        "vectorized": total_docs,
        "conversations": treated,
        "remaining": remaining,
        "errors": errors,
        **stats,
    }


def _vectorize_one_conversation(conv_id: str) -> tuple[int, str | None]:
    """Vectorise une conversation et la marque indexee (non destructive).

    Retourne (nombre de documents indexes, erreur | None). Aucun None silencieux :
    l'erreur est toujours une chaine explicite ou None. La conversation source
    est conservee ; seul un marqueur `indexed` evite le retraitement infini.
    """
    conversations, _, vector, analytics = _ctx()
    conv = conversations.get_conversation(conv_id)
    if not conv or "messages" not in conv:
        return 0, "Conversation introuvable"

    texts = [msg.get("content", "").strip() for msg in conv["messages"]]
    texts = [text for text in texts if text]
    if not texts:
        conversations.mark_indexed(conv_id)
        return 0, None

    pairs = [(text, {"source": "conversation", "conv_id": conv_id}) for text in texts]
    vector.index_batch(pairs)
    vector.vectorize_pending()
    conversations.mark_indexed(conv_id)
    analytics.track_query(agent="vectorize", model=EXPECTED_MODEL, success=True)
    return len(texts), None


@router.post("/api/ingest")
def ingest_documents(body: IngestRequest):
    _, log, vector, _ = _ctx()
    documents = body.documents
    source = body.source
    if not documents:
        return JSONResponse({"error": "Liste 'documents' vide", "ingested": 0}, status_code=400)
    pairs = []
    for doc in documents:
        text = doc.text
        metadata = doc.metadata or {}
        if text:
            metadata["source"] = source
            pairs.append((text, metadata))
    vector.index_batch(pairs)
    log.log("INFO", f"Ingested {len(pairs)} documents from '{source}'")
    return {"status": "ok", "ingested": len(pairs)}


@router.post("/api/vectorize")
def vectorize_pending():
    _, log, vector, _ = _ctx()
    count = vector.vectorize_pending()
    stats = vector.stats()
    log.log("INFO", f"Vectorisation: {count} documents traites")
    return {"status": "ok", "vectorized": count, **stats}


@router.get("/api/vectorize")
async def vectorize_stats():
    # stats() lit des compteurs en mémoire : safe en async.
    _, _, vector, _ = _ctx()
    return vector.stats()


# Borne maximale pour la pagination (évite les requêtes déraisonnables)
SEARCH_MAX_LIMIT = 100


@router.get("/api/search")
def search_documents(q: str = "", top_k: int = 20, limit: int = 20, offset: int = 0):
    # Laisse sync : recherche vectorielle CPU-bound (bloquerait la boucle d'événements en async).
    _, _, vector, _ = _ctx()
    if not q.strip():
        return JSONResponse({"error": "Parametre 'q' requis", "results": []}, status_code=400)
    # Bornes de pagination : limite plafonnée à 100, offset et limite >= 0
    limit = min(max(int(limit), 0), SEARCH_MAX_LIMIT)
    offset = max(int(offset), 0)
    # Récupère assez de résultats pour couvrir la page demandée (troncature en Python)
    results = vector.search(q, top_k=offset + limit)
    total = len(results)
    page = results[offset:offset + limit]
    # Scrub PII sur les textes renvoyés (emails, IPs, credentials) — jamais en clair.
    for r in page:
        if isinstance(r, dict) and "text" in r:
            r["text"] = scrub(r["text"])
    return {
        "query": q,
        "results": page,
        "total": total,
        "count": len(page),
        "limit": limit,
        "offset": offset,
    }
