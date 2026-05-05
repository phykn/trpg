import json

import pytest
from pydantic import ValidationError

from src.game.domain.memory import (
    ActLogEntry,
    BonusItem,
    GMLogEntry,
    PlayerLogEntry,
    RollLogEntry,
)
from src.wire.emit import emit_log_entry
from src.wire.models import LogEntryPayload


def test_gm_envelope():
    log = GMLogEntry(id=1, kind="gm", text="당신 앞에 문이 있습니다.")
    ev = emit_log_entry(log)
    assert ev["type"] == "log_entry"
    assert ev["data"]["kind"] == "gm"
    assert ev["data"]["id"] == 1
    assert ev["data"]["text"] == "당신 앞에 문이 있습니다."


def test_player_envelope():
    log = PlayerLogEntry(id=2, kind="player", text="문을 엽니다.")
    ev = emit_log_entry(log)
    assert ev["type"] == "log_entry"
    assert ev["data"]["kind"] == "player"
    assert ev["data"]["id"] == 2
    assert ev["data"]["text"] == "문을 엽니다."


def test_act_envelope():
    log = ActLogEntry(id=3, kind="act", text="문을 발로 찼습니다.")
    ev = emit_log_entry(log)
    assert ev["type"] == "log_entry"
    assert ev["data"]["kind"] == "act"


def test_roll_envelope():
    log = RollLogEntry(
        id=4,
        kind="roll",
        check="STR DC 12",
        roll=14,
        margin=2,
        result="success",
        bonus_breakdown=[BonusItem(label="근력", value=2), BonusItem(label="장비", value=1)],
    )
    ev = emit_log_entry(log)
    assert ev["type"] == "log_entry"
    assert ev["data"]["kind"] == "roll"
    assert ev["data"]["check"] == "STR DC 12"
    assert ev["data"]["roll"] == 14
    assert ev["data"]["margin"] == 2
    assert ev["data"]["result"] == "success"
    assert len(ev["data"]["bonus_breakdown"]) == 2
    assert ev["data"]["bonus_breakdown"][0]["label"] == "근력"
    assert ev["data"]["bonus_breakdown"][0]["value"] == 2


def test_root_model_dump_unwraps():
    """RootModel.model_dump() yields the inner discriminated dict directly,
    not {'root': ...}. emit_log_entry depends on this."""
    log = GMLogEntry(id=99, kind="gm", text="t")
    payload = LogEntryPayload(root=log)
    dumped = payload.model_dump()
    assert "root" not in dumped
    assert dumped["kind"] == "gm"
    assert dumped["id"] == 99


def test_discriminator_validates_kind():
    """LogEntryPayload's discriminated union rejects malformed input
    (e.g. roll-only field on a gm entry)."""
    with pytest.raises(ValidationError):
        LogEntryPayload(root={"id": 1, "kind": "gm", "roll": 5})


def test_serializable_to_json():
    log = RollLogEntry(
        id=1, kind="roll", check="WIS DC 10",
        roll=12, margin=2, result="partial",
        bonus_breakdown=[],
    )
    ev = emit_log_entry(log)
    s = json.dumps(ev, ensure_ascii=False)
    assert "WIS DC 10" in s
    assert "partial" in s


def test_roll_result_literal_preserved():
    """`result` Literal[success|partial|fail] survives serialization."""
    for result_value in ("success", "partial", "fail"):
        log = RollLogEntry(
            id=0, kind="roll", check="x",
            roll=1, margin=0, result=result_value,
            bonus_breakdown=[],
        )
        ev = emit_log_entry(log)
        assert ev["data"]["result"] == result_value
