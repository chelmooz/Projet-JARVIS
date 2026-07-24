"""LlmResponseJudge — Juge isolé (Verifier Sub-Agent).

Évalue la qualité d'une réponse RAG sans voir le raisonnement de l'acteur.
Respecte SKILL.md §6 : isolation stricte entre acteur et vérificateur.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.constants import DEFAULT_MODEL
from services.adapters.protocols import LLMAdapter

_logger = logging.getLogger("jarvis.rag_judge")

JUDGE_THRESHOLD = 0.8

JUDGE_SYSTEM_PROMPT = """\
Tu es un évaluateur neutre. Tu ne vois que la requête, les documents \
fournis et la réponse finale. Tu ne connais pas le processus interne.

Retourne UNIQUEMENT un objet JSON valide :
{"score": <float entre 0.0 et 1.0>, "reason": "<justification concise>"}

Critères :
- Pertinence : la réponse adresse-t-elle la requête ?
- Fondement : la réponse s'appuie-t-elle sur les documents fournis ?
- Actionnabilité : la réponse propose-t-elle des actions concrètes ?
"""

JUDGE_USER_TEMPLATE = """\
## Requête
{query}

## Documents fournis
{chunks_block}

## Réponse à évaluer
{response}
"""


class JudgeParseError(Exception):
    """Exception levée quand la réponse du juge n'est pas un JSON valide ou complet."""


class LlmResponseJudge:
    """Juge isolé qui évalue une réponse RAG via un LLM.

    Ne voit que : requête + chunks + réponse finale.
    Ne voit PAS : raisonnement de l'acteur, étapes intermédiaires.
    """

    def __init__(self, llm_adapter: LLMAdapter, model: str = DEFAULT_MODEL) -> None:
        self._llm = llm_adapter
        self._model = model

    def evaluate(
        self, query: str, chunks: list[str], response: str
    ) -> dict[str, Any]:
        """Évalue la qualité d'une réponse.

        Retourne {"score": float, "reason": str}.
        Lève JudgeParseError si le résultat est invalide.
        """
        raw = self._call_judge_llm(query, chunks, response)
        parsed = self._parse_judge_output(raw)
        return self._normalize_score(parsed)

    # ─── Construction du prompt ───────────────────────────────────────

    def _build_prompt(self, query: str, chunks: list[str], response: str) -> str:
        """Construit le prompt du juge (sans raisonnement de l'acteur)."""
        chunks_block = self._format_chunks(chunks)
        user_part = JUDGE_USER_TEMPLATE.format(
            query=query,
            chunks_block=chunks_block,
            response=response,
        )
        return f"{JUDGE_SYSTEM_PROMPT}\n\n{user_part}"

    def _format_chunks(self, chunks: list[str]) -> str:
        """Formate les chunks en bloc texte numéroté."""
        if not chunks:
            return "(aucun document fourni)"
        return "\n".join(f"- [{i}] {chunk}" for i, chunk in enumerate(chunks, 1))

    # ─── Appel LLM ────────────────────────────────────────────────────

    def _call_judge_llm(self, query: str, chunks: list[str], response: str) -> str:
        """Appelle le LLM et extrait la chaîne de réponse."""
        prompt = self._build_prompt(query, chunks, response)
        raw = self._llm.query(prompt, self._model)
        return self._extract_text(raw)

    def _extract_text(self, raw: Any) -> str:
        """Extrait la chaîne de texte d'une réponse LLM brute."""
        if hasattr(raw, "data") and isinstance(raw.data, dict):
            return raw.data.get("response", str(raw))
        if isinstance(raw, dict):
            return raw.get("response", str(raw))
        return str(raw)

    # ─── Parsing et validation ────────────────────────────────────────

    def _parse_judge_output(self, raw_text: str) -> dict[str, Any]:
        """Parse le JSON du juge. Lève JudgeParseError si invalide."""
        cleaned = self._strip_markdown_fence(raw_text)
        parsed = self._decode_json(cleaned)
        self._validate_required_fields(parsed)
        return parsed

    def _strip_markdown_fence(self, text: str) -> str:
        """Retire les balises ```json ... ``` si présentes."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            inner = lines[1:-1] if len(lines) > 2 else lines[1:]
            return "\n".join(inner).strip()
        return stripped

    def _decode_json(self, text: str) -> dict[str, Any]:
        """Décode une chaîne JSON. Lève JudgeParseError si échec."""
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise JudgeParseError(
                f"JSON invalide retourné par le juge : {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise JudgeParseError(
                f"Le juge a retourné un {type(result).__name__}, attendu dict"
            )
        return result

    def _validate_required_fields(self, parsed: dict[str, Any]) -> None:
        """Vérifie que 'score' et 'reason' sont présents."""
        if "score" not in parsed:
            raise JudgeParseError("Champ 'score' manquant dans la réponse du juge")
        if "reason" not in parsed:
            raise JudgeParseError("Champ 'reason' manquant dans la réponse du juge")
        if not isinstance(parsed["score"], (int, float)):
            raise JudgeParseError(
                f"Champ 'score' doit être numérique, reçu {type(parsed['score']).__name__}"
            )

    # ─── Normalisation ────────────────────────────────────────────────

    def _normalize_score(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Clampe le score entre 0.0 et 1.0."""
        score = float(parsed["score"])
        clamped = max(0.0, min(1.0, score))
        return {"score": clamped, "reason": str(parsed["reason"])}