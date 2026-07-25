"""Tests pour compute_composite_score — score composite feedback + juge + récidive."""
import pytest

from services.score import compute_composite_score


class TestComputeCompositeScore:
    def test_good_feedback_and_high_judge(self):
        score = compute_composite_score("👍", 0.9)
        assert score == pytest.approx(0.6 * 0.9 + 0.4 * 1.0)

    def test_bad_feedback_and_low_judge(self):
        score = compute_composite_score("👎", 0.3)
        assert score == pytest.approx(0.6 * 0.3 + 0.4 * 0.0)

    def test_no_feedback_and_medium_judge(self):
        score = compute_composite_score(None, 0.5)
        assert score == pytest.approx(0.6 * 0.5 + 0.4 * 0.5)

    def test_recidive_penalty(self):
        score = compute_composite_score("👍", 0.9, recidive=True)
        expected = 0.6 * 0.9 + 0.4 * 1.0 - 0.3
        assert score == pytest.approx(expected)

    def test_score_clamped_to_zero(self):
        score = compute_composite_score("👎", 0.0, recidive=True)
        assert score == 0.0

    def test_score_clamped_to_one(self):
        score = compute_composite_score("👍", 1.0)
        assert score == 1.0
