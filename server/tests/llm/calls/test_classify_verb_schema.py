import pytest
from pydantic import ValidationError

from src.llm.calls.classify.schema import Verb, RefuseReason, JudgeOutput


def test_verb_basic_shape():
    v = Verb(name="move", target_ids=[], modifiers={"destination": "loc_01"})
    assert v.name == "move"
    assert v.modifiers["destination"] == "loc_01"


def test_verb_unknown_name_rejected():
    with pytest.raises(ValidationError):
        Verb(name="invalid_verb_name", target_ids=[])


def test_verb_target_ids_max_length():
    with pytest.raises(ValidationError):
        Verb(name="attack", target_ids=["a"] * 9)


def test_refuse_reason_message_required():
    with pytest.raises(ValidationError):
        RefuseReason(category="out_of_game", message_hint="")


def test_judge_output_actions_only():
    out = JudgeOutput(actions=[Verb(name="wait")])
    assert out.refuse is None
    assert len(out.actions) == 1


def test_judge_output_refuse_only():
    out = JudgeOutput(
        refuse=RefuseReason(category="out_of_game", message_hint="범위 밖")
    )
    assert out.actions is None


def test_judge_output_exactly_one_required():
    with pytest.raises(ValidationError):
        JudgeOutput()


def test_judge_output_both_set_rejected():
    with pytest.raises(ValidationError):
        JudgeOutput(
            actions=[Verb(name="wait")],
            refuse=RefuseReason(category="out_of_game", message_hint="x"),
        )


def test_judge_output_empty_actions_rejected():
    with pytest.raises(ValidationError):
        JudgeOutput(actions=[])


def test_judge_output_actions_max_length():
    with pytest.raises(ValidationError):
        JudgeOutput(actions=[Verb(name="wait")] * 5)
