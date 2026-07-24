"""Router FastAPI — Point d'entrée principal, monte les sous-routeurs.

Ce module agit comme le Composition Root de l'application FastAPI.
Il assemble les dépendances, enregistre les routeurs et expose l'app.

Dettes signalées (non corrigées ici) :
- Les routes système inline (``/``, ``/api/status``, ``/api/backend``,
  ``/api/models``, ``/api/metrics``, ``/{path:path}``) devraient être extraites
  vers ``controllers/routes/system.py`` (SRP : le router monte les routeurs,
  il ne définit pas d'endpoints).
- La structure du dict de status (``_build_status``) est une réimplémentation
  suite à la suppression des globales legacy de ``context.py`` ; à valider
  contre le contrat attendu par le frontend (static/).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config.constants import REFRESH_INTERVAL, VERSION
from config.paths import STATIC_DIR
from controllers.context import _ctx, build_app
from controllers.responses import ok
from controllers.routes import agents as agents_routes
from controllers.routes import analytics as analytics_routes
from controllers.routes import beta_dashboard as beta_dashboard_routes
from controllers.routes import code_review as code_review_routes
from controllers.routes import conversations as conv_routes
from controllers.routes import diagnostic as diagnostic_routes
from controllers.routes import documents as doc_routes
from controllers.routes import files as files_routes
from controllers.routes import jarvis as jarvis_routes
from controllers.routes import kill_coding as kill_coding_routes
from controllers.routes import pipelines as pipelines_routes
from controllers.routes import quality_audit as quality_audit_routes
from controllers.routes import settings as settings_routes
from controllers.routes import skills as skills_routes
from controllers.static_cache import serve_cached_file
from services.profiling import get_slow_endpoints


def _service_healthy(service: Any) -> bool:
    """État de santé défensif d'un service (``is_healthy()`` optionnel)."""
    check = getattr(service, "is_healthy", None)
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        _logger.warning("Service health check failed", exc_info=True)
        return False


def _build_status(context: Any) -> dict[str, Any]:
    """Construit le dict de status à partir du contexte (état des services).

    Remplace les globales legacy ``_check_ollama`` / ``_refresh_status_cache``
    de l'ancien ``context.py`` : l'état est dérivé des ports (``ping`` /
    ``is_healthy``), sans état global mutable.
    """
    inference = getattr(context, "inference", None)
    ollama_up = False
    if inference is not None and hasattr(inference, "ping"):
        try:
            ollama_up = bool(inference.ping())
        except Exception:
            _logger.warning("Inference ping failed", exc_info=True)
            ollama_up = False
    return {
        "ollama": ollama_up,
        "inference": _service_healthy(inference),
        "vector": _service_healthy(getattr(context, "vector", None)),
        "memory": _service_healthy(getattr(context, "memory", None)),
        "conversations": _service_healthy(getattr(context, "conversations", None)),
        "version": VERSION,
    }


def _get_context(request: Request) -> Any:
    """Retourne le contexte applicatif de la requête.

    Utilise ``app.state.context`` (posé par le ``lifespan``, cf.
    ``controllers/warmup.py``) une fois l'application démarrée. En dehors du
    cycle de vie complet de l'app (ex. ``TestClient`` instancié sans
    ``with``, tests qui construisent l'app sans déclencher le lifespan), on
    retombe sur le singleton de compatibilité ``controllers.context._ctx``
    afin que les fixtures de test qui le mutent directement restent prises
    en compte.
    """
    context = getattr(request.app.state, "context", None)
    if context is not None:
        return context
    from controllers.context import _ctx
    return _ctx


def _mount_router(app: FastAPI, router: Any) -> None:
    """Monte un sous-routeur directement dans la liste des routes de l'app.

    Équivalent fonctionnel à ``app.include_router(router)`` pour nos besoins :
    aucun de nos sous-routeurs n'utilise ``prefix``/``dependencies`` au
    niveau du routeur (les éventuels ``tags`` sont déjà portés par les routes
    elles-mêmes, cf. ``controllers/routes/settings.py``).

    Contourne volontairement ``include_router`` : les versions récentes de
    FastAPI enveloppent chaque routeur inclus dans un objet interne
    paresseux (``_IncludedRouter``) qui casse l'introspection directe de
    ``app.routes`` (utilisée par ``scripts/check_api_contract.py`` pour la
    détection de drift front/back). Étendre directement la liste conserve
    des ``APIRoute`` réels : dispatch identique, mais introspectables.
    """
    app.router.routes.extend(router.routes)


async def get_backend() -> dict[str, str]:
    return {"backend": "ollama"}


async def get_metrics(request: Request) -> dict[str, Any]:
    context = _get_context(request)
    return ok(context.metrics.get_metrics())


def list_models(request: Request) -> dict[str, Any]:
    """Liste les modèles disponibles (reste sync : appel réseau Ollama bloquant)."""
    context = _get_context(request)
    inference = getattr(context, "inference", None)
    if inference is None:
        return {"models": [], "available": False, "error": "Backend inférence non initialisé."}
    models = inference.list_models()
    return {"models": models, "available": True}


def index(request: Request):
    """Sert la page d'accueil (reste sync : lecture disque statique)."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    resp = serve_cached_file(index_path, request)
    if resp is not None:
        return resp
    return {"message": "JARVIS API — voir /docs pour la documentation"}


def get_status(request: Request) -> dict[str, Any]:
    """Renvoie le status agrégé (reste sync : appel réseau Ollama bloquant)."""
    context = _get_context(request)
    cache = request.app.state.status_cache
    lock = request.app.state.status_lock
    with lock:
        data = cache["data"] if time.time() - cache["ts"] < REFRESH_INTERVAL else None
    if data is None:
        status = _build_status(context)
        with lock:
            cache["data"] = status
            cache["ts"] = time.time()
            data = status
    data = dict(data)
    data["slow_endpoints"] = get_slow_endpoints()
    return ok(data)


def serve_static(path: str, request: Request):
    """Sert les fichiers statiques avec protection path traversal.

    Reste sync (module-level) : lecture disque statique.
    """
    full_path = os.path.join(STATIC_DIR, path)
    resolved = os.path.abspath(full_path)
    static_root = os.path.abspath(STATIC_DIR)
    if not (resolved == static_root or resolved.startswith(static_root + os.sep)):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if os.path.isfile(resolved):
        resp = serve_cached_file(resolved, request)
        if resp is not None:
            return resp
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


def create_app() -> FastAPI:
    """Factory de création de l'application FastAPI (Composition Root)."""
    app = build_app()

    # Contexte applicatif exposé dès la création (pas seulement au lifespan) :
    # `get_app_context`/`Depends(get_app_context)` et les tests qui manipulent
    # directement le singleton `_ctx` (sans déclencher le lifespan, ex.
    # `TestClient(app)` sans `with`) doivent trouver un contexte valide.
    # Le lifespan (`controllers/warmup.py`) ne réassigne rien si déjà présent.
    app.state.context = _ctx

    # Cache de status attaché à l'app (pas de globale mutable).
    app.state.status_cache = {"data": None, "ts": 0.0}
    app.state.status_lock = threading.Lock()

    # Enregistrement des routeurs métier.
    for sub_router in (
        jarvis_routes.router,
        agents_routes.router,
        conv_routes.router,
        diagnostic_routes.router,
        doc_routes.router,
        analytics_routes.router,
        files_routes.router,
        pipelines_routes.router,
        code_review_routes.router,
        kill_coding_routes.router,
        quality_audit_routes.router,
        settings_routes.router,
        skills_routes.router,
    ):
        _mount_router(app, sub_router)

    # Beta dashboard (opt-in).
    if os.environ.get("JARVIS_BETA_DASHBOARD") == "1":
        _mount_router(app, beta_dashboard_routes.router)

    # --- Routes système inline (dette : à extraire vers routes/system.py) ---
    app.get("/api/backend")(get_backend)
    app.get("/api/models")(list_models)
    app.get("/", response_model=None)(index)
    app.get("/api/status")(get_status)
    app.get("/api/metrics")(get_metrics)
    # Enregistrement de la fonction module-level (plus de closure)
    app.get("/{path:path}", response_model=None)(serve_static)

    return app


# Exposition pour uvicorn.
app = create_app()


# ==============================================================================
# STUB LEGACY POUR COMPATIBILITÉ DES TESTS (NE PAS UTILISER EN PRODUCTION)
# ==============================================================================
def _check_ollama() -> bool:
    """Stub pour test_profiling.py — vérifie si Ollama répond.

    Anciennement : globale mutable dans context.py, utilisée par le router
    pour construire le cache de status. Supprimée lors du refacto (injection
    via app.state + _build_status). Conservée comme stub pour ne pas casser
    la collection de test_profiling.py qui fait :
        _ORIG_ROUTER_CHECK = _router_mod._check_ollama
    """
    try:
        from services.inference import InferenceService
        return InferenceService().ping()
    except Exception:
        return False


__all__ = ["create_app", "app", "_check_ollama"]
