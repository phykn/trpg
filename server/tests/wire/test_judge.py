import json

import pytest
from pydantic import ValidationError

from src.domain.verb import RefuseReason, Verb
from src.wire.emit import (
    emit_judge_pending_check_trigger,
    emit_judge_refuse,
    emit_judge_verb,
    emit_judge_verbs,
)
from src.wire.models import (
    JudgePayload,
    JudgeVerb,
)


def test_pending_check_trigger_envelope():
    ev = emit_judge_pending_check_trigger(
        tier="normal", stat="STR", targets=["loc1"], reason="문이 잠겼습니다."
    )
    assert ev["type"] == "judge"
    assert ev["data"]["judge_kind"] == "pending_check_trigger"
    assert ev["data"]["tier"] == "normal"
    assert ev["data"]["stat"] == "STR"
    assert ev["data"]["targets"] == ["loc1"]
    assert ev["data"]["reason"] == "문이 잠겼습니다."


def test_refuse_envelope():
    refuse = RefuseReason(category="out_of_game", message_hint="규칙 외 행동입니다.")
    ev = emit_judge_refuse(refuse)
    assert ev["type"] == "judge"
    assert ev["data"]["judge_kind"] == "refuse"
    assert ev["data"]["refuse"]["category"] == "out_of_game"
    assert ev["data"]["refuse"]["message_hint"] == "규칙 외 행동입니다."


def test_verb_envelope():
    verb = Verb(name="speak", target_ids=["npc_a"], modifiers={"tone": "polite"})
    ev = emit_judge_verb(verb)
    assert ev["type"] == "judge"
    assert ev["data"]["judge_kind"] == "verb"
    assert ev["data"]["verb"]["name"] == "speak"
    assert ev["data"]["verb"]["target_ids"] == ["npc_a"]
    assert ev["data"]["verb"]["modifiers"] == {"tone": "polite"}


def test_verbs_envelope():
    v1 = Verb(name="move", target_ids=["loc1"])
    v2 = Verb(name="speak", target_ids=["npc_a"])
    ev = emit_judge_verbs([v1, v2])
    assert ev["type"] == "judge"
    assert ev["data"]["judge_kind"] == "verbs"
    assert len(ev["data"]["actions"]) == 2
    assert ev["data"]["actions"][0]["name"] == "move"
    assert ev["data"]["actions"][1]["name"] == "speak"


def test_root_model_dump_unwraps():
    """RootModel.model_dump() yields the inner discriminated dict directly,
    not {'root': ...}. emit_judge_* helpers depend on this."""
    payload = JudgePayload(
        root=JudgeVerb(
            judge_kind="verb",
            verb=Verb(name="rest", target_ids=[]),
        )
    )
    dumped = payload.model_dump()
    assert "root" not in dumped
    assert dumped["judge_kind"] == "verb"


def test_discriminator_validates_kind():
    """JudgePayload's discriminated union rejects mismatched judge_kind+shape."""
    with pytest.raises(ValidationError):
        JudgePayload(
            root={
                "judge_kind": "verb",
                "refuse": {"category": "out_of_game", "message_hint": "x"},
            }
        )


def test_serializable_to_json():
    ev = emit_judge_pending_check_trigger(
        tier="hard", stat="DEX", targets=["t1", "t2"], reason="민첩 판정"
    )
    s = json.dumps(ev, ensure_ascii=False)
    assert "민첩 판정" in s
    assert "judge_kind" in s


def test_targets_list_copy_independence():
    """emit_judge_pending_check_trigger should defensively copy targets."""
    src = ["a", "b"]
    ev = emit_judge_pending_check_trigger(
        tier="easy", stat="WIS", targets=src, reason="r"
    )
    src.append("c")
    assert ev["data"]["targets"] == ["a", "b"]


def test_actions_list_copy_independence():
    src = [Verb(name="wait", target_ids=[])]
    ev = emit_judge_verbs(src)
    src.append(Verb(name="rest", target_ids=[]))
    assert len(ev["data"]["actions"]) == 1
