import pytest
from pydantic import ValidationError

from src.domain.entities import EQUIPMENT_SLOTS, Equipment, Skill, Stats
from src.domain.memory import (
    GMLogEntry,
    LogEntry,
    Memory,
    PendingCheck,
    RollLogEntry,
)


def test_stats_defaults_and_bounds():
    s = Stats()
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        assert getattr(s, k) == 10
    with pytest.raises(ValidationError):
        Stats(STR=21)


def test_equipment_slot_order():
    assert EQUIPMENT_SLOTS == ("weapon", "armor", "accessory")
    e = Equipment(weapon="sword_01")
    assert e.weapon == "sword_01"
    assert e.armor is None


def test_memory_target_id_optional():
    m = Memory(content="x", importance=2, turn=1)
    assert m.target_id is None
    m2 = Memory(content="x", importance=1, turn=1, target_id="guard_01")
    assert m2.target_id == "guard_01"


def test_pending_check_required_roll_bounds():
    base = dict(
        player_input="x",
        tier="normal",
        stat="CHA",
        target="g",
        targets=["g"],
        dc=10,
        mod=0,
        reason="설득",
        created_at="2026-04-26",
    )
    PendingCheck(required_roll=20, **base)
    with pytest.raises(ValidationError):
        PendingCheck(required_roll=21, **base)


def test_log_entry_discriminator():
    from pydantic import TypeAdapter

    ad = TypeAdapter(LogEntry)
    gm = ad.validate_python({"id": 1, "kind": "gm", "text": "..."})
    roll = ad.validate_python(
        {
            "id": 2,
            "kind": "roll",
            "check": "x",
            "roll": 12,
            "margin": 5,
            "result": "success",
        }
    )
    assert isinstance(gm, GMLogEntry)
    assert isinstance(roll, RollLogEntry) and roll.roll == 12


def test_roll_log_accepts_three_results():
    from pydantic import TypeAdapter, ValidationError

    ad = TypeAdapter(LogEntry)
    base = {"id": 1, "kind": "roll", "check": "x", "roll": 11, "margin": 1}
    for r in ("success", "partial", "fail"):
        ad.validate_python({**base, "result": r})
    with pytest.raises(ValidationError):
        ad.validate_python({**base, "result": "critical"})


def test_skill_enums():
    Skill(id="s", name="x", type="buff", target="self", primary_stat="DEX")
    with pytest.raises(ValidationError):
        Skill(id="s", name="x", type="invalid_type", target="self", primary_stat="DEX")
