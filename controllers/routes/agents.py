"""Routes Agents — Profils, assignation, vision.

Dettes signalées (non corrigées ici) :
- ``handle_vision`` retourne le ``AgentRunResult`` brut (non enveloppé dans
  ``ok()``) et ses erreurs utilisent une structure ad hoc (``{error, agent}``)
  plutôt que la convention ``{data, error}`` : le frontend attend cette forme
  plate. À trancher avec le contrat frontend.
- ``log`` / ``analytics`` sont accédés via le contexte complet faute de helpers
  granulaires dans ``context.py`` (seuls inference/memory/vector/agents/
  orchestrator en ont). À ajouter pour cohérence DIP.
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from config.paths import CONFIG_DIR, PROFILES_FILE
from controllers.context import get_app_context, _ctx
from controllers.di import AppContext
from controllers.responses import fail, ok
from models.schemas import AssignRequest, VisionRequest
from services.sanitize import safe_model_name
from services.selector import select_vision_model

_logger = logging.getLogger(__name__)

PREFERENCES_PATH = CONFIG_DIR / "model_preferences.json"
TOKEN_ESTIMATE_DIVISOR = 4  # estimation grossière : ~4 caractères par token

# Exposition de services au niveau module (Étape 9 fusionnée)
log = _ctx.log
analytics = _ctx.analytics

router = APIRouter()


PROFILE_TO_ROUTING = {
    "orchestrateur": "dev",
    "techlead":      "dev",
    "devops":        "network",
    "designer":      "vision",
    "datasecu":      "cyber",
}


def _sync_agent_model_to_preferences(profile_key: str, model_name: str) -> None:
    """Synchronise le modèle assigné (agent_profiles.json → model_preferences.json)."""
    try:
        with open(PREFERENCES_PATH, encoding="utf-8") as f:
            prefs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        _logger.warning("model_preferences.json illisible/absent, repart de zéro: %s", e)
        prefs = {}
    routing_key = PROFILE_TO_ROUTING.get(profile_key, profile_key)
    prefs.setdefault("model_map", {})[routing_key] = model_name
    prefs.setdefault("agent_to_profile", {})[routing_key] = profile_key
    prefs["default_model"] = model_name
    with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=4, ensure_ascii=False)


@router.get("/api/agents")
def list_profiles():
    """Liste les profils d'agents (I/O bloquant → threadpool FastAPI)."""
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            profiles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        _logger.warning("agent_profiles.json illisible/absent: %s", e)
        return fail("Profiles not found", status_code=500)
    return ok({
        "profiles": profiles.get("profiles", {}),
        "agent_model_map": profiles.get("agent_model_map", {}),
    })


@router.post("/api/agents/assign")
def assign_profile(body: AssignRequest):
    """Assigne un modèle à un profil (I/O bloquant → threadpool FastAPI)."""
    profile_key = body.profile
    model_name = safe_model_name(body.model)
    if not model_name:
        return fail(f"Modèle invalide: {body.model!r}", status_code=400)
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            profiles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        _logger.warning("agent_profiles.json illisible/absent: %s", e)
        return fail("Profiles file not found", status_code=500)
    if profile_key not in profiles.get("profiles", {}):
        return fail(f"Profil '{profile_key}' introuvable", status_code=404)
    profiles["profiles"][profile_key]["model"] = model_name
    profiles["agent_model_map"][profile_key] = model_name
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=4, ensure_ascii=False)
    _sync_agent_model_to_preferences(profile_key, model_name)
    _logger.info("Profile assigned: %s -> %s", profile_key, model_name)
    return ok({"profile": profile_key, "model": model_name})


@router.get("/api/vision")
async def vision_info():
    """Documentation de l'endpoint vision."""
    return {
        "endpoint": "POST /api/vision",
        "body": '{"image": "data:image/png;base64,...", "task": "optionnel"}',
    }


@router.post("/api/vision")
def handle_vision(body: VisionRequest, context: AppContext = Depends(get_app_context)):
    """Analyse une image via l'agent vision (appel LLM bloquant → threadpool FastAPI)."""
    image = body.image
    task = body.task
    start = time.time()
    if not image:
        return JSONResponse({"error": "Aucune image fournie", "agent": "vision"}, status_code=400)
    inference = context.inference
    if inference is None:
        return JSONResponse(
            {"error": "Backend non initialisé (Ollama portable injoignable).", "agent": "vision"},
            status_code=503,
        )
    vision_agent = context.agents.get("vision") if isinstance(context.agents, dict) else None
    if vision_agent is None:
        return JSONResponse(
            {"error": "Agent vision non disponible (init des agents en échec).", "agent": "vision"},
            status_code=503,
        )
    model_name = select_vision_model(inference)
    if not model_name:
        return JSONResponse(
            {"error": "Aucun modèle vision disponible",
             "solution": "Vérifiez que LLaVA est dans models/", "agent": "vision"},
            status_code=503,
        )
    vision_context = {"image": image}
    try:
        result = vision_agent.run(task, model_name, vision_context)
    except Exception:
        _logger.error("Vision failed", exc_info=True)
        return JSONResponse({"error": "Erreur interne de l'agent vision", "agent": "vision"}, status_code=500)
    context.memory.update_habits({"task": task, "agent": "vision"})
    latency = round((time.time() - start) * 1000, 1)
    context.analytics.track_query(
        agent="vision", model=model_name,
        tokens_in=len(task) // TOKEN_ESTIMATE_DIVISOR,
        tokens_out=len(str(result.get("response", ""))) // TOKEN_ESTIMATE_DIVISOR,
        latency_ms=latency, success=result.get("error") is None,
    )
    context.log.log("INFO", f"agent=vision model={model_name}")
    return result


__all__ = ["router"]
