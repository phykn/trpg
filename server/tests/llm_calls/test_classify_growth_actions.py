import pytest
from pydantic import ValidationError

from src.llm_calls.classify.schema import (
    CancelGrowthAction,
    GrowthPendingAction,
    output_adapter,
)


def test_growth_pending_action_validates():
    action = GrowthPendingAction(action="growth_pending")
    assert action.action == "growth_pending"


def test_cancel_growth_action_validates():
    action = CancelGrowthAction(action="cancel_growth")
    assert action.action == "cancel_growth"


def test_judge_output_accepts_growth_pending():
    parsed = output_adapter.validate_python({"action": "growth_pending"})
    assert isinstance(parsed, GrowthPendingAction)


def test_judge_output_accepts_cancel_growth():
    parsed = output_adapter.validate_python({"action": "cancel_growth"})
    assert isinstance(parsed, CancelGrowthAction)


def test_growth_pending_rejects_extra_fields():
    with pytest.raises(ValidationError):
        GrowthPendingAction(action="growth_pending", extra="x")  # type: ignore[call-arg]
