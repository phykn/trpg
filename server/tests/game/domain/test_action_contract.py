import pytest
from pydantic import ValidationError

from src.game.domain.action import Action, ActionCheckHint, ActionOutput


def test_action_accepts_from_and_with_aliases():
    action = Action.model_validate(
        {
            "verb": "transfer",
            "what": "sword_01",
            "from": "<self>.inventory",
            "to": "<self>.equipped.weapon",
            "with": "both_hands",
            "how": "free",
        }
    )

    assert action.from_ == "<self>.inventory"
    assert action.with_ == "both_hands"
    dumped = action.model_dump(by_alias=True)
    assert dumped["from"] == "<self>.inventory"
    assert dumped["with"] == "both_hands"


def test_action_rejects_result_fields():
    with pytest.raises(ValidationError, match="success"):
        Action.model_validate({"verb": "attack", "what": "goblin_01", "success": True})


def test_action_rejects_legacy_cast_as_top_level_action():
    with pytest.raises(ValidationError):
        Action.model_validate({"verb": "cast", "with": "minor_heal_01"})


def test_action_output_actions_only():
    out = ActionOutput(actions=[Action(verb="pass")])
    assert out.refuse is None
    assert len(out.actions or []) == 1


def test_action_output_refuse_only():
    out = ActionOutput(
        refuse={
            "category": "out_of_game",
            "message_hint": "범위 밖",
            "target": "npc_01",
        }
    )
    assert out.actions is None
    assert out.refuse is not None
    assert out.refuse.target == "npc_01"


def test_action_output_exactly_one_required():
    with pytest.raises(ValidationError):
        ActionOutput()


def test_action_output_both_set_rejected():
    with pytest.raises(ValidationError):
        ActionOutput(
            actions=[Action(verb="pass")],
            refuse={"category": "out_of_game", "message_hint": "x"},
        )


def test_action_output_empty_actions_rejected():
    with pytest.raises(ValidationError):
        ActionOutput(actions=[])


def test_action_output_actions_max_length():
    with pytest.raises(ValidationError):
        ActionOutput(actions=[Action(verb="pass")] * 5)


def test_action_check_hint_requires_reason_when_required():
    with pytest.raises(ValidationError):
        ActionCheckHint(required=True)
