import json
import pytest
from pydantic import ValidationError

from src.llm.calls.classify.errors import ModifierValidationError
from src.llm.calls.classify.schema import validate_judge_output


def test_actions_one_verb():
    raw = json.dumps({"actions": [{"name": "wait", "modifiers": {"stance": "idle"}}]})
    out = validate_judge_output(raw, in_combat=False)
    assert out.actions[0].name == "wait"


def test_refuse_alone():
    raw = json.dumps({"refuse": {"category": "out_of_game", "message_hint": "x"}})
    out = validate_judge_output(raw, in_combat=False)
    assert out.actions is None


def test_modifier_validation_raised():
    raw = json.dumps({"actions": [{"name": "move", "modifiers": {}}]})
    with pytest.raises(ModifierValidationError):
        validate_judge_output(raw, in_combat=False)


def test_silent_drop_unknown_modifier():
    raw = json.dumps({
        "actions": [{
            "name": "speak",
            "modifiers": {"intent": "friendly", "target": "n", "ghost_key": "x"},
        }]
    })
    out = validate_judge_output(raw, in_combat=False)
    assert "ghost_key" not in out.actions[0].modifiers


def test_pydantic_error_for_unknown_verb():
    raw = json.dumps({"actions": [{"name": "fly", "modifiers": {}}]})
    with pytest.raises(ValidationError):
        validate_judge_output(raw, in_combat=False)


def test_in_combat_move_without_destination():
    raw = json.dumps({"actions": [{"name": "move", "modifiers": {"manner": "hasty"}}]})
    out = validate_judge_output(raw, in_combat=True)
    assert out.actions[0].name == "move"


def test_out_of_combat_move_without_destination_fails():
    raw = json.dumps({"actions": [{"name": "move", "modifiers": {"manner": "hasty"}}]})
    with pytest.raises(ModifierValidationError):
        validate_judge_output(raw, in_combat=False)


def test_empty_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_judge_output("", in_combat=False)


def test_whitespace_only_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_judge_output("  \n  ", in_combat=False)
