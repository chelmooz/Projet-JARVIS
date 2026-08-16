"""Client Ollama local pour génération JSON et gestion VRAM."""

from __future__ import annotations

import os
from typing import Any

import httpx

from agents.parsing import extract_json


def _ollama_url() -> str:
    return os.environ.get("JARVIS_OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _model() -> str:
    return os.environ.get("JARVIS_OLLAMA_MODEL", "qwen2.5:7b")


def generate_json(prompt: str, system: str | None = None) -> dict[str, Any] | None:
    """Envoie prompt à Ollama, extrait et retourne le JSON de la réponse.

    Retourne ``None`` si : erreur HTTP, réponse vide, JSON non extractible.
    Ne lève jamais d'exception.
    """
    payload: dict[str, Any] = {"model": _model(), "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    try:
        response = httpx.post(
            f"{_ollama_url()}/api/generate",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, OSError):
        return None
    text = data.get("response", "")
    if not text:
        return None
    return extract_json(text)


def unload() -> bool:
    """Décharge le modèle de la VRAM (``keep_alive: 0``).

    Retourne ``True`` si succès, ``False`` sinon. Ne lève jamais d'exception.
    """
    try:
        response = httpx.post(
            f"{_ollama_url()}/api/generate",
            json={"model": _model(), "keep_alive": 0},
            timeout=10.0,
        )
        response.raise_for_status()
        return True
    except (httpx.HTTPError, ValueError, OSError):
        return False
