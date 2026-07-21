"""Routes JARVIS — Endpoint principal POST /api/jarvis et helpers."""
import asyncio
import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models.schemas import JarvisRequest
from services.sanitize import clean_text, validate_base64_image
from services.selector import read_preferences

MAX_TEXT_LENGTH = 10000
MAX_IMAGE_MB = 4
TRUNCATE_CONV_ID = 64

router = APIRouter()


def _ctx():
    """Lazy import : les singletons ne sont disponibles qu'apres build_app().

    BUG CORRIGE (2026-07-11) : un `from controllers.context import orchestrator`
    au niveau module capturait la valeur (None) AVANT que build_app() n'appelle
    _ctx.initialize()/_sync_module_globals() dans controllers/router.py, car
    ce fichier est importe avant `app = build_app()`. Consequence : orchestrator
    restait None pour toujours en production, meme apres une init reussie
    ("Erreur interne: 'NoneType' object has no attribute 'handle_request'"),
    invisible en tests car ceux-ci monkeypatchaient directement l'attribut de
    module (deja casse) plutot que de passer par le vrai flux d'init.
    """
    from controllers.context import analytics, conversations, orchestrator
    return orchestrator, analytics, conversations


def _save_conv(conv_id, task, result, agent_key, conversations_svc):
    if not conv_id:
        return
    try:
        conversations_svc.add_message(conv_id, "user", task)
        resp = result.get("response") if isinstance(result, dict) else str(result)
        conversations_svc.add_message(conv_id, "assistant", resp or "",
                                      agent=result.get("agent", agent_key),
                                      model=result.get("model"))
    except Exception as e:
        logging.getLogger("api").error("save_conv failed: %s", e)


def _track_query(agent_key, model_name, result, start, analytics_svc, task=""):
    """Enregistre les metriques d'une requete.

    Fix P1 #8 (audit 2026-07-21) : tokens_in doit refleter la tache envoyee
    par l'utilisateur, pas la reponse du modele — sinon les analytics
    tokens_in/tokens_out sont identiques et faux (les deux calcules sur
    `result["response"]`).
    """
    latency = round((time.time() - start) * 1000, 1)
    analytics_svc.track_query(
        agent=agent_key, model=model_name,
        tokens_in=len(str(task)) // 4,
        tokens_out=len(str(result.get("response", ""))) // 4,
        latency_ms=latency, success=result.get("error") is None,
    )


@router.get("/api/jarvis")
async def jarvis_info():
    """Documentation des endpoints disponibles."""
    return {
        "endpoints": {
            "POST /api/jarvis": "Envoyer une tache a JARVIS",
            "GET /api/status": "Statut des services",
            "POST /api/vision": "Analyser une image",
            "GET /api/agents": "Liste des profils",
            "POST /api/agents/assign": "Assigner un modele a un profil",
            "POST /api/ingest": "Ingerer des documents",
            "GET /api/conversations": "Lister les conversations",
            "POST /api/conversations": "Creer une conversation",
            "GET /api/analytics": "Statistiques d'usage",
            "GET /api/cyber/workflows": "Workflows cybersecurite",
            "GET /api/pipelines": "Lister les pipelines disponibles",
            "POST /api/pipelines/run": "Executer un pipeline",
            "GET /api/backend": "Backend actif",
            "POST /api/backend/select": "Changer de backend",
            "GET /api/metrics": "Metriques d'usage et uptime",
            "GET /api/models": "Modeles disponibles sur le backend actif",
            "GET /api/settings": "Lire les preferences utilisateur",
            "PUT /api/settings": "Modifier une preference utilisateur",
            "POST /api/files/authorize": "Autoriser un dossier pour analyse",
            "DELETE /api/files/authorize": "Revoquer un dossier",
            "GET /api/files/authorized": "Lister dossiers autorises",
            "POST /api/files/list": "Lister contenu d'un dossier",
            "POST /api/files/read": "Lire un fichier (max 10 Ko)",
            "POST /api/files/find": "Chercher fichiers par pattern glob",
        }
    }


@router.post("/api/jarvis")
async def handle_request(body: JarvisRequest):
    try:
        prefs = read_preferences()
        if prefs.get("offline", False):
            return {
                "response": "Mode hors-ligne active. Desactivez le mode hors-ligne dans les parametres.",
                "agent": "system",
                "model": "offline",
                "backend": "offline",
            }
        orchestrator, analytics, conversations = _ctx()
        if orchestrator is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "JARVIS n'est pas encore pret (services non initialises — "
                             "Ollama injoignable ou init en echec). Reessayez dans quelques secondes.",
                    "agent": "system", "model": "unknown",
                },
            )
        task = clean_text(body.task, MAX_TEXT_LENGTH)
        image = body.image
        if image and not validate_base64_image(image, max_mb=MAX_IMAGE_MB):
            image = None
        conv_id = body.conversation_id
        if conv_id:
            conv_id = conv_id.strip()[:TRUNCATE_CONV_ID]
        start = time.time()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, orchestrator.handle_request, task, image, conv_id
        )
        agent_key = result.get("agent", "unknown")
        model_name = result.get("model", "auto")
        _track_query(agent_key, model_name, result, start, analytics, task=task)
        _save_conv(conv_id, task, result, agent_key, conversations)
        return result
    except Exception as e:
        import traceback
        logging.getLogger("api").error("handle_request crashed: %s\n%s", e, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur interne: {e}", "agent": "system", "model": "unknown"},
        )
