"""Utilitaires de parsing JSON partagés par les agents.

Les modèles Ollama répondent parfois avec du texte autour du JSON
(````` ```json ``...`` ``` ```` ou des préfixes). ``extract_json`` nettoie
la réponse ; ``parse_model`` valide via Pydantic et retourne ``None``
plutôt que de lever (fallback géré par l'appelant).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """Extrait un objet JSON d'une réponse LLM.

    Priorité : bloc ```json ... ```, puis bloc ``` ... ```, puis premier
    objet JSON au premier `{` et dernier `}`.
    """
    if not text:
        return None
    for match in _JSON_BLOCK_RE.finditer(text):
        candidate = match.group(1).strip()
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    stripped = text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def parse_model[T: BaseModel](model_cls: type[T], text: str) -> T | None:
    """Valide la réponse LLM contre un modèle Pydantic.

    Retourne ``None`` si le JSON est absent/invalide ou ne valide pas —
    l'appelant applique son fallback.
    """
    payload = extract_json(text)
    if payload is None:
        return None
    try:
        return model_cls.model_validate(payload)
    except ValueError:
        return None
