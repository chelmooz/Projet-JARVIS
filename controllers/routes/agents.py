"""Routes Agents — Profils, assignation, vision."""
import json
import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.constants import PROJECT_DIR
from controllers.context import PROFILES_PATH, agents, analytics, inference, log, memory
from controllers.responses import fail, ok
from models.schemas import AssignRequest, VisionRequest
from services.sanitize import safe_model_name
from services.selector import select_vision_model

PREFERENCES_PATH = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
TOKEN_ESTIMATE_DIVISOR = 4

router = APIRouter()


PROFILE_TO_ROUTING = {
    "orchestrateur": "dev",
    "techlead":      "dev",
    "devops":        "network",
    "designer":      "vision",
    "datasecu":      "cyber",
}


def _sync_agent_model_to_preferences(profile_key: str, model_name: str):
    """Synchronise le modèle assigné dans agent_profiles.json vers model_preferences.json."""
    try:
        with open(PREFERENCES_PATH, encoding="utf-8") as f:
            prefs = json.load(f)
    except Exception as e:
        log.log("DEBUG", f"model_preferences.json illisible/absent, repart de zero: {e}")
        prefs = {}
    routing_key = PROFILE_TO_ROUTING.get(profile_key, profile_key)
    prefs.setdefault("model_map", {})[routing_key] = model_name
    prefs.setdefault("agent_to_profile", {})[routing_key] = profile_key
    prefs["default_model"] = model_name
    with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=4, ensure_ascii=False)


@router.get("/api/agents")
def list_profiles():
    # Laisse sync : lit le fichier agent_profiles.json (I/O bloquant).
    try:
        with open(PROFILES_PATH, encoding="utf-8") as f:
            profiles = json.load(f)
    except Exception as e:
        log.log("DEBUG", f"agent_profiles.json illisible/absent: {e}")
        return fail("Profiles not found", status_code=500)
    return ok({
        "profiles": profiles.get("profiles", {}),
        "agent_model_map": profiles.get("agent_model_map", {}),
    })


@router.post("/api/agents/assign")
def assign_profile(body: AssignRequest):
    profile_key = body.profile
    model_name = safe_model_name(body.model)
    if not model_name:
        return JSONResponse({"error": f"Modele invalide: {body.model!r}"}, status_code=400)
    try:
        with open(PROFILES_PATH, encoding="utf-8") as f:
            profiles = json.load(f)
    except Exception as e:
        log.log("DEBUG", f"agent_profiles.json illisible/absent: {e}")
        return JSONResponse({"error": "Profiles file not found"}, status_code=500)
    if profile_key not in profiles.get("profiles", {}):
        return JSONResponse({"error": f"Profil '{profile_key}' introuvable"}, status_code=404)
    profiles["profiles"][profile_key]["model"] = model_name
    profiles["agent_model_map"][profile_key] = model_name
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=4, ensure_ascii=False)
    _sync_agent_model_to_preferences(profile_key, model_name)
    log.log("INFO", f"Profile assigned: {profile_key} -> {model_name}")
    return {"status": "ok", "profile": profile_key, "model": model_name}


@router.get("/api/vision")
async def vision_info():
    return {
        "endpoint": "POST /api/vision",
        "body": '{"image": "data:image/png;base64,...", "task": "optionnel"}',
    }


@router.post("/api/vision")
def handle_vision(body: VisionRequest):
    image = body.image
    task = body.task
    start = time.time()
    if not image:
        return JSONResponse({"error": "Aucune image fournie"}, status_code=400)
    if inference is None:
        return JSONResponse({"error": "Backend non initialise (Ollama portable injoignable).",
                             "agent": "vision"}, status_code=503)
    vision_agent = agents.get("vision") if isinstance(agents, dict) else None
    if vision_agent is None:
        return JSONResponse({"error": "Agent vision non disponible (init des agents en echec).",
                             "agent": "vision"}, status_code=503)
    model_name = select_vision_model(inference)
    if not model_name:
        return JSONResponse({"error": "Aucun modele vision disponible",
                             "solution": "Verifiez que LLaVA est dans models/",
                             "agent": "vision"}, status_code=503)
    context = {"image": image}
    try:
        result = vision_agent.run(task, model_name, context)
    except Exception as e:
        log.log("ERROR", f"Vision failed: {e}")
        return JSONResponse({"error": str(e), "agent": "vision"}, status_code=500)
    memory.update_habits({"task": task, "agent": "vision"})
    latency = round((time.time() - start) * 1000, 1)
    analytics.track_query(agent="vision", model=model_name,
                          tokens_in=len(task) // TOKEN_ESTIMATE_DIVISOR,
                          tokens_out=len(str(result.get("response", ""))) // TOKEN_ESTIMATE_DIVISOR,
                          latency_ms=latency, success=result.get("error") is None)
    log.log("INFO", f"agent=vision model={model_name}")
    return result
