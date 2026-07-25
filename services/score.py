"""Score composite — combine feedback, jugement LLM et récidive (ADR-008 §3).

Fonction pure, sans état ni effet de bord — testable isolément.
"""

from config.constants import (
    FEEDBACK_ABSENT,
    FEEDBACK_THUMBS_DOWN,
    FEEDBACK_THUMBS_UP,
    JUDGE_WEIGHT,
    FEEDBACK_WEIGHT,
    RECIDIVE_PENALTY,
)

_FEEDBACK_MAP: dict[str | None, float] = {
    "👍": FEEDBACK_THUMBS_UP,
    "👎": FEEDBACK_THUMBS_DOWN,
}


def compute_composite_score(
    feedback: str | None,
    judge_score: float,
    recidive: bool = False,
) -> float:
    """Calcule le score composite pour la rétropropagation.

    Formule : JUDGE_WEIGHT * judge_score + FEEDBACK_WEIGHT * feedback_score
    Pénalité RECIDIVE_PENALTY si récidive.
    Clampé dans [0.0, 1.0].
    """
    feedback_score = _FEEDBACK_MAP.get(feedback, FEEDBACK_ABSENT)
    raw = JUDGE_WEIGHT * judge_score + FEEDBACK_WEIGHT * feedback_score
    if recidive:
        raw += RECIDIVE_PENALTY
    return max(0.0, min(1.0, raw))


__all__ = ["compute_composite_score"]
