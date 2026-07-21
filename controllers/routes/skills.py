"""Routes Skills — Gestion des skills activables injectés dans le contexte."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.paths import SKILLS_CONFIG
from services.file_utils import write_json_atomic
from services.skills import get_enabled_skills_text, load_skills

router = APIRouter()


@router.get("/api/skills")
def list_skills():
    # Laisse sync : load_skills() lit SKILLS_CONFIG sur le disque (I/O bloquant).
    """Liste tous les skills avec leur statut enabled/disabled."""
    data = load_skills()
    return {
        "skills": data.get("skills", []),
        "enabled_ids": [s["id"] for s in data.get("skills", []) if s.get("enabled")],
    }


@router.get("/api/skills/context")
def skills_context():
    # Laisse sync : get_enabled_skills_text() lit SKILLS_CONFIG sur le disque (I/O bloquant).
    """Retourne le texte concaténé des skills activés (injecté dans le system prompt)."""
    return {"context": get_enabled_skills_text()}


@router.post("/api/skills/toggle")
def toggle_skill(body: dict):
    """Active ou désactive un skill par son id."""
    skill_id = body.get("skill_id")
    if not skill_id:
        return JSONResponse({"error": "skill_id requis"}, status_code=400)
    data = load_skills()
    for skill in data.get("skills", []):
        if skill["id"] == skill_id:
            skill["enabled"] = not skill.get("enabled", False)
            write_json_atomic(SKILLS_CONFIG, data, indent=2)
            return {"status": "ok", "skill_id": skill_id, "enabled": skill["enabled"]}
    return JSONResponse({"error": f"Skill '{skill_id}' introuvable"}, status_code=404)
