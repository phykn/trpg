import pytest

from src.llm_calls.classify.schema import (
    CancelGrowthAction,
    GrowthPendingAction,
)
from src.llm_calls.classify.semantics import check_semantics, JudgeSemanticError


def _surroundings(can_level_up: bool, pending_growth: dict | None) -> dict:
    return {
        "growth": {"can_level_up": can_level_up, "xp_pool": 100},
        "pending_growth": pending_growth,
        "entities": [],
        "merchants": [],
        "skill_candidates": [],
    }


def test_growth_pending_requires_can_level_up():
    output = GrowthPendingAction(action="growth_pending")
    surroundings = _surroundings(can_level_up=False, pending_growth=None)
    with pytest.raises(JudgeSemanticError):
        check_semantics(output, surroundings)


def test_growth_pending_passes_when_can_level_up():
    output = GrowthPendingAction(action="growth_pending")
    surroundings = _surroundings(can_level_up=True, pending_growth=None)
    check_semantics(output, surroundings)  # no raise


def test_cancel_growth_requires_pending_growth():
    output = CancelGrowthAction(action="cancel_growth")
    surroundings = _surroundings(can_level_up=True, pending_growth=None)
    with pytest.raises(JudgeSemanticError):
        check_semantics(output, surroundings)


def test_cancel_growth_passes_when_pending_growth_set():
    output = CancelGrowthAction(action="cancel_growth")
    surroundings = _surroundings(
        can_level_up=True, pending_growth={"stage": "asking_stat"}
    )
    check_semantics(output, surroundings)  # no raise
