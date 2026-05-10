import json

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.schema import validate_action_output_json


def test_validate_accepts_action_move_json():
    raw = json.dumps({"actions": [{"verb": "move", "to": "loc_01"}]})

    out = validate_action_output_json(raw, in_combat=False)

    assert out.actions[0].verb == "move"
    assert out.actions[0].to == "loc_01"


def test_validate_accepts_action_pass_json_as_wait():
    raw = json.dumps({"actions": [{"verb": "pass", "note": "잠시 숨을 고른다."}]})

    out = validate_action_output_json(raw, in_combat=False)

    assert out.actions[0].verb == "pass"
    assert out.actions[0].note == "잠시 숨을 고른다."


def test_validate_rejects_internal_verb_json():
    raw = json.dumps({"actions": [{"name": "wait"}]})

    with pytest.raises(ValidationError, match="verb"):
        validate_action_output_json(raw, in_combat=False)


def test_invalid_action_json_raises_validation_error():
    raw = json.dumps({"actions": [{"verb": "attack", "success": True}]})

    with pytest.raises(ValidationError, match="success"):
        validate_action_output_json(raw, in_combat=False)
