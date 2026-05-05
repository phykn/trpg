import json

import pytest
from pydantic import ValidationError

from src.wire.emit import emit_combat_end, emit_combat_start, emit_combat_turn
from src.wire.models import CombatTurnPayload


# combat_start

def test_combat_start_envelope():
    ev = emit_combat_start(
        turn_order=["p1", "e1"], round=1, surprise=None, enemy_ids=["e1"]
    )
    assert ev["type"] == "combat_start"
    assert ev["data"]["turn_order"] == ["p1", "e1"]
    assert ev["data"]["round"] == 1
    assert ev["data"]["surprise"] is None
    assert ev["data"]["enemy_ids"] == ["e1"]


def test_combat_start_surprise_player():
    ev = emit_combat_start(
        turn_order=["p1"], round=1, surprise="player", enemy_ids=["e1"]
    )
    assert ev["data"]["surprise"] == "player"


def test_combat_start_defensive_list_copy():
    src = ["p1", "e1"]
    ev = emit_combat_start(turn_order=src, round=1, surprise=None, enemy_ids=["e1"])
    src.append("e2")
    assert ev["data"]["turn_order"] == ["p1", "e1"]


# combat_turn

def test_combat_turn_from_payload_object():
    payload = CombatTurnPayload(
        actor="p1", action="attack", round=1,
        grade="success", damage=5, killed=False,
        target="e1", skill_name=None, skill_id=None,
    )
    ev = emit_combat_turn(payload)
    assert ev["type"] == "combat_turn"
    assert ev["data"]["actor"] == "p1"
    assert ev["data"]["action"] == "attack"
    assert ev["data"]["damage"] == 5
    assert ev["data"]["item_id"] is None  # default


def test_combat_turn_from_dict_validates():
    """emit_combat_turn accepts auto-combat's _turn_event dict shape."""
    tev = {
        "actor": "p1", "action": "attack", "grade": "success",
        "damage": 5, "killed": False, "target": "e1",
        "skill_name": None, "skill_id": None, "round": 1,
    }
    ev = emit_combat_turn(tev)
    assert ev["data"]["actor"] == "p1"
    assert ev["data"]["item_id"] is None


def test_combat_turn_with_item_id():
    """Player passive equip/unequip path includes item_id."""
    payload = CombatTurnPayload(
        actor="p1", action="equip", round=2, item_id="sword1"
    )
    ev = emit_combat_turn(payload)
    assert ev["data"]["item_id"] == "sword1"
    assert ev["data"]["damage"] == 0  # default
    assert ev["data"]["killed"] is False  # default


def test_combat_turn_dict_missing_required_field_raises():
    """Dict missing the `actor` field fails validation."""
    bad = {"action": "attack", "round": 1}
    with pytest.raises(ValidationError):
        emit_combat_turn(bad)


# combat_end

def test_combat_end_envelope():
    ev = emit_combat_end("victory")
    assert ev == {"type": "combat_end", "data": {"outcome": "victory"}}


def test_combat_end_all_outcomes():
    for outcome in ("victory", "defeat", "downed", "fled"):
        ev = emit_combat_end(outcome)
        assert ev["data"]["outcome"] == outcome


def test_combat_end_invalid_outcome_raises():
    with pytest.raises(ValidationError):
        emit_combat_end("inconclusive")


# JSON serializable

def test_envelopes_serializable():
    s = json.dumps(emit_combat_start(turn_order=["p1"], round=1, surprise=None, enemy_ids=[]))
    s += json.dumps(emit_combat_turn(CombatTurnPayload(actor="p1", action="wait", round=1)))
    s += json.dumps(emit_combat_end("victory"))
    assert "combat_start" in s
    assert "combat_turn" in s
    assert "combat_end" in s


def test_combat_turn_payload_field_order():
    """CombatTurnPayload field-order matches what _turn_event produces +
    the item_id append. This documents the schema for site #4 migration."""
    payload = CombatTurnPayload(actor="p1", action="x", round=1)
    keys = list(payload.model_dump().keys())
    expected_prefix = ["actor", "action", "round", "grade", "damage", "killed",
                       "target", "skill_name", "skill_id"]
    assert keys[:9] == expected_prefix
    assert keys[9] == "item_id"
