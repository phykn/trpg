import json

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.schema import validate_action_output_json


def test_actions_one_verb():
    raw = json.dumps({"actions": [{"verb": "pass"}]})
    out = validate_action_output_json(raw, in_combat=False)
    assert out.actions[0].verb == "pass"


def test_refuse_alone():
    raw = json.dumps({"refuse": {"category": "out_of_game", "message_hint": "x"}})
    out = validate_action_output_json(raw, in_combat=False)
    assert out.actions is None


def test_modifier_violation_raises_validation_error():
    raw = json.dumps({"actions": [{"verb": "move"}]})
    with pytest.raises(ValidationError):
        validate_action_output_json(raw, in_combat=False)


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
        validate_action_output_json(raw, in_combat=False)


def test_unknown_verb_rejected():
    raw = json.dumps({"actions": [{"verb": "fly"}]})
    with pytest.raises(ValidationError):
        validate_action_output_json(raw, in_combat=False)


def test_query_rejected():
    raw = json.dumps({"actions": [{"verb": "query"}, {"verb": "pass"}]})
    with pytest.raises(ValidationError):
        validate_action_output_json(raw, in_combat=False)


def test_in_combat_move_without_destination():
    raw = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    out = validate_action_output_json(raw, in_combat=True)
    assert out.actions[0].verb == "move"


def test_in_combat_attack_accepts_without_tactic():
    raw = json.dumps({"actions": [{"verb": "attack", "what": "enemy_01"}]})
    out = validate_action_output_json(raw, in_combat=True)
    assert out.actions[0].how is None


def test_out_of_combat_attack_rejects_tactic():
    raw = json.dumps(
        {"actions": [{"verb": "attack", "what": "enemy_01", "how": "attack"}]}
    )
    with pytest.raises(ValidationError):
        validate_action_output_json(raw, in_combat=False)


def test_out_of_combat_move_without_destination_fails():
    raw = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    with pytest.raises(ValidationError):
        validate_action_output_json(raw, in_combat=False)


def test_empty_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_action_output_json("", in_combat=False)


def test_whitespace_only_answer_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        validate_action_output_json("  \n  ", in_combat=False)
