import pytest
from pydantic import ValidationError

from src.llm_calls.classify.schema import (
    DismissAction,
    RecruitAction,
    output_adapter,
)


def test_recruit_action_valid():
    a = RecruitAction(action="recruit", target="npc.edric")
    assert a.target == "npc.edric"


def test_recruit_action_rejects_extra_fields():
    with pytest.raises(ValidationError):
        RecruitAction(action="recruit", target="npc.edric", extra="x")


def test_dismiss_action_valid():
    a = DismissAction(action="dismiss", target="npc.edric")
    assert a.target == "npc.edric"


def test_judge_output_validates_recruit():
    raw = {"action": "recruit", "target": "npc.edric"}
    parsed = output_adapter.validate_python(raw)
    assert isinstance(parsed, RecruitAction)


def test_judge_output_validates_dismiss():
    raw = {"action": "dismiss", "target": "npc.edric"}
    parsed = output_adapter.validate_python(raw)
    assert isinstance(parsed, DismissAction)


def test_recruit_not_chainable():
    """recruit cannot appear as a chain part."""
    raw = {
        "action": "chain",
        "parts": [
            {"action": "pass"},
            {"action": "recruit", "target": "npc.edric"},
        ],
    }
    with pytest.raises(ValidationError):
        output_adapter.validate_python(raw)
