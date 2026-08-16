"""Tests des utilitaires de parsing JSON des agents (MT-Lot12-L1).

Couvre ``agents.parsing`` : extraction JSON robuste des réponses LLM
(bloc ```json``, texte autour du JSON, JSON cassé) et validation Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.parsing import extract_json, parse_model


class _EvalResult(BaseModel):
    """Modèle Pydantic minimal de test (forme d'un résultat d'évaluation)."""

    score: float = Field(ge=0.0, le=1.0)
    reason: str


def test_json_valide_parse_en_modele() -> None:
    text = '{"score": 0.85, "reason": "réponse pertinente"}'
    result = parse_model(_EvalResult, text)
    assert result is not None
    assert result.score == 0.85
    assert result.reason == "réponse pertinente"


def test_json_noye_dans_du_texte_extrait_et_parse() -> None:
    text = (
        "Voici mon analyse :\n"
        "```json\n"
        '{"score": 0.42, "reason": "partiellement correct"}\n'
        "```\n"
        "J'espère que cela t'aide."
    )
    result = parse_model(_EvalResult, text)
    assert result is not None
    assert result.score == 0.42
    assert result.reason == "partiellement correct"
    assert extract_json("préfixe {'score': 1, 'reason': 'x'} suffixe") is None


def test_json_casse_retourne_none() -> None:
    assert parse_model(_EvalResult, '{"score": 0.5, "reason": "inachevé') is None
    assert parse_model(_EvalResult, "pas de JSON du tout") is None
    assert parse_model(_EvalResult, "") is None
