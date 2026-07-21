"""Routes Skills — Gestion des skills activables injectés dans le contexte."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.paths import SKILLS_CONFIG
from controllers.responses import fail, ok
from services.file_utils import write_json_atomic
from services.skills import get_enabled_skills_text, load_skills

router = APIRouter()


class ToggleSkillRequest(BaseModel):
    skill_id: str


@router.get("/api/skills")
def list_skills() -> dict:
    """Liste tous les skills avec leur statut enabled/disabled.

    Laisse sync : ``load_skills()`` lit SKILLS_CONFIG sur le disque (I/O bloquant).
    """
    data = load_skills()
    skills = data.get("skills", [])
    return ok({
        "skills": skills,
        "enabled_ids": [s["id"] for s in skills if s.get("enabled")],
    })


@router.get("/api/skills/context")
def skills_context() -> dict:
    """Retourne le texte concaténé des skills activés (injecté dans le system prompt).

    Laisse sync : ``get_enabled_skills_text()`` lit SKILLS_CONFIG sur le disque (I/O bloquant).
    """
    return ok({"context": get_enabled_skills_text()})


@router.post("/api/skills/toggle")
def toggle_skill(body: ToggleSkillRequest) -> dict | JSONResponse:
    """Active ou désactive un skill par son id."""
    skill_id = body.skill_id
    data = load_skills()
    for skill in data.get("skills", []):
        if skill["id"] == skill_id:
            skill["enabled"] = not skill.get("enabled", False)
            write_json_atomic(SKILLS_CONFIG, data, indent=2)
            return ok({"skill_id": skill_id, "enabled": skill["enabled"]})
    return fail(f"Skill '{skill_id}' introuvable", status_code=404)


__all__ = ["router"]
