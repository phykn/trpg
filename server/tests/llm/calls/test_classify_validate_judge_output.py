import json

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.schema import validate_judge_output


def test_actions_one_verb():
    raw = json.dumps({"actions": [{"verb": "pass"}]})
    out = validate_judge_output(raw, in_combat=False)
    assert out.actions[0].name == "wait"


def test_refuse_alone():
    raw = json.dumps({"refuse": {"category": "out_of_game", "message_hint": "x"}})
    out = validate_judge_output(raw, in_combat=False)
    assert out.actions is None


def test_modifier_violation_raises_validation_error():
    raw = json.dumps({"actions": [{"verb": "move"}]})
    with pytest.raises(ValidationError):
        validate_judge_output(raw, in_combat=False)


def test_unknown_action_field_rejected():
    raw = json.dumps(
        {
            "actions": [
                {
                    "verb": "speak",
                    "how": "friendly",
                    "to": "n",
                    "ghost_key": "x",
                }
            ]
        }
    )
    with pytest.raises(ValidationError, match="ghost_key"):
        validate_judge_output(raw, in_combat=False)


def test_unknown_verb_rejected():
    raw = json.dumps({"actions": [{"verb": "fly"}]})
    with pytest.raises(ValidationError):
        validate_judge_output(raw, in_combat=False)


def test_query_cannot_be_chained():
    raw = json.dumps({"actions": [{"verb": "query"}, {"verb": "pass"}]})
    with pytest.raises(ValidationError, match="query"):
        validate_judge_output(raw, in_combat=False)


def test_in_combat_move_without_destination():
    raw = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    out = validate_judge_output(raw, in_combat=True)
    assert out.actions[0].name == "move"


def test_out_of_combat_move_without_destination_fails():
    raw = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    with pytest.raises(ValidationError):
        validate_judge_output(raw, in_combat=False)


def test_empty_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_judge_output("", in_combat=False)


def test_whitespace_only_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_judge_output("  \n  ", in_combat=False)
