from config.constants import (
    FEEDBACK_ABSENT,
    FEEDBACK_THUMBS_DOWN,
    FEEDBACK_THUMBS_UP,
    FEEDBACK_WEIGHT,
    JUDGE_WEIGHT,
    RECIDIVE_PENALTY,
)
from services.score import compute_composite_score


def test_score_feedback_absent() -> None:
    expected = JUDGE_WEIGHT * 0.5 + FEEDBACK_WEIGHT * FEEDBACK_ABSENT
    assert compute_composite_score(None, 0.5) == expected


def test_thumbs_order() -> None:
    up = compute_composite_score("👍", 0.5)
    none = compute_composite_score(None, 0.5)
    down = compute_composite_score("👎", 0.5)
    assert up > none > down
    assert "👍" in {"👍", "👎"}  # garde-fou constants présents
    assert FEEDBACK_THUMBS_UP > FEEDBACK_ABSENT > FEEDBACK_THUMBS_DOWN


def test_recidive_penalty() -> None:
    assert compute_composite_score(None, 0.5, True) < compute_composite_score(None, 0.5, False)
    # la pénalité est bien RECIDIVE_PENALTY
    base = JUDGE_WEIGHT * 0.5 + FEEDBACK_WEIGHT * FEEDBACK_ABSENT
    assert compute_composite_score(None, 0.5, True) == max(0.0, min(1.0, base + RECIDIVE_PENALTY))


def test_clamp_upper() -> None:
    assert compute_composite_score(None, 100.0) == 1.0


def test_clamp_lower() -> None:
    assert compute_composite_score(None, -100.0) == 0.0
