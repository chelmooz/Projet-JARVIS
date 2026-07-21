"""Router FastAPI — Point d'entrée principal, monte les sous-routeurs.

Ce module est volontairement minimal : toute la logique métier
a été extraite dans services/orchestrator.py.
"""
import os
import sys
import time

from config.bootstrap import ensure_project_root

ensure_project_root()

# ruff: isort: off
try:
    from fastapi import Request  # noqa: E402
    from fastapi.responses import JSONResponse  # noqa: E402
    from config.constants import PROJECT_DIR  # noqa: E402
    from controllers.static_cache import serve_cached_file  # noqa: E402
    from controllers.context import (  # noqa: E402
        REFRESH_INTERVAL, _check_ollama, _refresh_status_cache, build_app, cache_lock,
        get_context, status_cache,
    )
    from controllers.routes import agents as agents_routes  # noqa: E402
    from controllers.routes import analytics as analytics_routes  # noqa: E402
    from controllers.routes import code_review as code_review_routes  # noqa: E402
    from controllers.routes import conversations as conv_routes  # noqa: E402
    from controllers.routes import diagnostic as diagnostic_routes  # noqa: E402
    from controllers.routes import documents as doc_routes  # noqa: E402
    from controllers.routes import files as files_routes  # noqa: E402
    from controllers.routes import jarvis as jarvis_routes  # noqa: E402
    from controllers.routes import kill_coding as kill_coding_routes  # noqa: E402
    from controllers.routes import pipelines as pipelines_routes  # noqa: E402
    from controllers.routes import quality_audit as quality_audit_routes  # noqa: E402
    from controllers.routes import settings as settings_routes  # noqa: E402
    from controllers.routes import skills as skills_routes  # noqa: E402
    from controllers.routes import beta_dashboard as beta_dashboard_routes  # noqa: E402

    from controllers.responses import ok  # noqa: E402
    from services.profiling import get_slow_endpoints  # noqa: E402
except ImportError as _imp_err:
    # sys.path portable (l.10-17) doit permettre ces imports ; s'il échoue, l'utilisateur
    # lance probablement le script hors de la racine de la clef USB.
    sys.stderr.write(
        "Erreur: modules JARVIS introuvables.\n"
        "Lancez jarvis.py depuis la racine du projet (dossier Projet-JARVIS sur la clef USB).\n"
        f"Detail: {_imp_err}\n"
    )
    raise
# ruff: isort: on

STATIC_DIR = os.path.join(PROJECT_DIR, "static")

# --- Construction de l'application FastAPI ---
app = build_app()

# Ré-route pour /api/jarvis depuis controllers.routes.jarvis
app.include_router(jarvis_routes.router)
app.include_router(agents_routes.router)
app.include_router(conv_routes.router)
app.include_router(diagnostic_routes.router)
app.include_router(doc_routes.router)
app.include_router(analytics_routes.router)
app.include_router(files_routes.router)
app.include_router(pipelines_routes.router)
app.include_router(code_review_routes.router)
app.include_router(kill_coding_routes.router)
app.include_router(quality_audit_routes.router)
app.include_router(settings_routes.router)
app.include_router(skills_routes.router)

# Beta dashboard route (mounted only when flagged)
if os.environ.get('JARVIS_BETA_DASHBOARD') == '1':
    app.include_router(beta_dashboard_routes.router)


@app.get("/api/backend")
async def get_backend():
    """Retourne le backend actif (Ollama, unique backend supporté)."""
    return {"backend": "ollama"}

@app.get("/api/models")
def list_models():
    # Laisse sync : list_models() fait un appel réseau bloquant à Ollama (/api/tags).
    # Le rendre async sans await n'apporterait rien ; à refactoriser en async plus tard.
    """Liste les modèles disponibles sur le backend actif."""
    inference = get_context().inference
    if inference is None:
        return {"models": [], "available": False,
                "error": "Backend inferieur non initialise (Ollama portable injoignable)."}
    return {"models": inference.list_models(), "available": True}

@app.get("/")
def index(request: Request):
    # Laisses sync : lit le disque via serve_cached_file() (I/O bloquant).
    """Page d'accueil : sert le fichier static/index.html s'il existe."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    resp = serve_cached_file(index_path, request)
    if resp is not None:
        return resp
    return {"message": "JARVIS API — voir /docs pour la documentation"}


@app.get("/api/status")
def get_status():
    # Laisses sync : _check_ollama() fait un appel réseau bloquant + cache_lock.
    # À refactoriser en async (await) si le backend devient async-friendly.
    """Statut des services backend : Ollama, mémoire, vecteur.

    Cache : rafraîchi toutes les 30 secondes maximum.
    """
    with cache_lock:
        data = status_cache["data"] if time.time() - status_cache["ts"] < REFRESH_INTERVAL else None
    if data is None:
        # _refresh_status_cache prend cache_lock en interne : on l'appelle
        # hors du bloc with pour éviter un deadlock (lock non réentrant).
        _refresh_status_cache(get_context(), cache_lock, _check_ollama())
        with cache_lock:
            data = status_cache["data"]
    # Copie pour ne pas polluer le cache partagé
    data = dict(data)
    data["slow_endpoints"] = get_slow_endpoints()
    return ok(data)


@app.get("/api/metrics")
async def get_metrics():
    # Métriques en mémoire + psutil (appels système non bloquants) : safe en async.
    """Retourne les métriques d'usage (uptime, requêtes, pipelines, erreurs)."""
    return ok(get_context().metrics.get_metrics())



# Catch-all placé EN DERNIER pour ne pas masquer les endpoints /api/* ci-dessus.
@app.get("/{path:path}")
def serve_static(path: str, request: Request):
    # Laisse sync : lit le disque via serve_cached_file() (I/O bloquant).
    """Sert les assets statiques à la racine (/monkey-engine.js, /index.html…).

    Ne touche pas aux endpoints API : seuls les fichiers présents dans
    STATIC_DIR sont servis, le reste renvoie 404.
    """
    full_path = os.path.join(STATIC_DIR, path)
    # S-1 : empêche le path traversal. On résout le chemin et on refuse tout
    # ce qui sort de STATIC_DIR (ex. "/../../etc/passwd") -> 404.
    resolved = os.path.abspath(full_path)
    static_root = os.path.abspath(STATIC_DIR)
    if not (resolved == static_root or resolved.startswith(static_root + os.sep)):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if os.path.isfile(resolved):
        return serve_cached_file(resolved, request)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})
