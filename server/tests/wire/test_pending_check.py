import json

from src.game.domain.entities import Character, Stats
from src.game.domain.memory import PendingCheck
from src.game.domain.state import GameState
from src.wire.emit import _build_pending_check_payload, emit_pending_check
from src.wire.models import PendingCheckPayload, TierBadge


def _state_with_player(stat_values: dict[str, int] | None = None) -> GameState:
    sv = stat_values or {}
    stats = Stats(
        STR=sv.get("STR", 10),
        DEX=sv.get("DEX", 10),
        CON=sv.get("CON", 10),
        INT=sv.get("INT", 10),
        WIS=sv.get("WIS", 10),
        CHA=sv.get("CHA", 10),
    )
    player = Character(id="p1", name="레오", race_id="human", stats=stats)
    state = GameState(game_id="game_test_001", profile="test", player_id="p1")
    state.characters["p1"] = player
    return state


def _pending(**overrides) -> PendingCheck:
    defaults = dict(
        player_input="t",
        kind="stat",
        tier="normal",
        stat="STR",
        target="loc1",
        targets=["loc1"],
        dc=10,
        mod=0,
        required_roll=10,
        reason="행동 판정",
        created_at="2026-05-05T00:00:00Z",
    )
    defaults.update(overrides)
    return PendingCheck(**defaults)


def test_payload_field_shape():
    state = _state_with_player({"STR": 14})
    pending = _pending(stat="STR", dc=12, mod=2, required_roll=10)
    payload = _build_pending_check_payload(state, pending)
    assert isinstance(payload, PendingCheckPayload)
    assert payload.kind == "stat"
    assert payload.dc == 12
    assert payload.stat == "STR"
    assert payload.stat_label == "근력"
    assert payload.stat_value == 14
    assert payload.mod == 2
    assert payload.required_roll == 10
    assert isinstance(payload.tier, TierBadge)
    assert payload.tier.label == "보통"
    assert payload.tier.max == 7
    assert payload.target == "loc1"
    assert payload.reason == "행동 판정"


def test_emit_wraps_envelope():
    state = _state_with_player()
    pending = _pending()
    ev = emit_pending_check(state, pending)
    assert ev["type"] == "pending_check"
    assert "data" in ev
    assert ev["data"]["kind"] == "stat"
    assert ev["data"]["stat_label"] == "근력"


def test_emit_serializable():
    state = _state_with_player()
    pending = _pending()
    ev = emit_pending_check(state, pending)
    json.dumps(ev, ensure_ascii=False)


def test_target_empty_string_passthrough():
    # domain PendingCheck.target is str (not optional); empty string is the
    # minimum non-None value and must pass through to the wire model unchanged.
    state = _state_with_player()
    pending = _pending(target="", targets=[])
    payload = _build_pending_check_payload(state, pending)
    assert payload.target == ""
