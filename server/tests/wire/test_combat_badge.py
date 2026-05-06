import json

from src.game.domain.entities import Character, Stats
from src.game.domain.state import CombatState, GameState
from src.wire.to_front import _build_combat_badge_payload


def _state(*, player_id="p1") -> GameState:
    state = GameState(game_id="game_dev", profile="dev", player_id=player_id)
    stats = Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10)
    state.characters[player_id] = Character(
        id=player_id,
        name="레오",
        race_id="race_human",
        stats=stats,
    )
    return state


def test_returns_none_when_no_combat():
    state = _state()
    assert _build_combat_badge_payload(state) is None


def test_returns_none_when_empty_turn_order():
    state = _state()
    state.combat_state = CombatState(
        turn_order=[], current_turn=0, round=1, enemy_ids=[]
    )
    assert _build_combat_badge_payload(state) is None


def test_player_turn_label():
    state = _state()
    state.combat_state = CombatState(
        turn_order=["p1", "e1"], current_turn=0, round=1, enemy_ids=["e1"]
    )
    state.characters["e1"] = Character(
        id="e1",
        name="고블린",
        race_id="race_human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=15,
    )
    payload = _build_combat_badge_payload(state)
    assert payload.turn_label == "내 차례"
    assert payload.round == 1


def test_enemy_turn_label():
    state = _state()
    state.combat_state = CombatState(
        turn_order=["p1", "e1"], current_turn=1, round=1, enemy_ids=["e1"]
    )
    state.characters["e1"] = Character(
        id="e1",
        name="고블린",
        race_id="race_human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=15,
    )
    payload = _build_combat_badge_payload(state)
    assert payload.turn_label == "고블린 차례"


def test_camel_case_serialization():
    state = _state()
    state.combat_state = CombatState(
        turn_order=["p1"], current_turn=0, round=1, enemy_ids=["e1"]
    )
    state.characters["e1"] = Character(
        id="e1",
        name="goblin",
        race_id="race_human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=15,
    )
    payload = _build_combat_badge_payload(state)
    dumped = payload.model_dump()
    assert "turnLabel" in dumped
    assert "turn_label" not in dumped
    assert dumped["enemies"][0]["hpMax"] == 15
    assert "hp_max" not in dumped["enemies"][0]


def test_enemies_skip_missing_character():
    state = _state()
    state.combat_state = CombatState(
        turn_order=["p1"], current_turn=0, round=1, enemy_ids=["e1", "ghost"]
    )
    state.characters["e1"] = Character(
        id="e1",
        name="goblin",
        race_id="race_human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=15,
    )
    payload = _build_combat_badge_payload(state)
    assert len(payload.enemies) == 1
    assert payload.enemies[0].name == "goblin"


def test_serializable_to_json():
    state = _state()
    state.combat_state = CombatState(
        turn_order=["p1"], current_turn=0, round=1, enemy_ids=["e1"]
    )
    state.characters["e1"] = Character(
        id="e1",
        name="고블린",
        race_id="race_human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=15,
    )
    payload = _build_combat_badge_payload(state)
    s = json.dumps(payload.model_dump(), ensure_ascii=False)
    assert "고블린" in s
    assert "turnLabel" in s
