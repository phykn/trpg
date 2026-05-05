"""B1 — inventory shows 금화(N) consistently, including N=0."""


from src.domain.entities import Character, Race
from src.domain.state import GameState
from src.mapping.to_front import to_hero, to_subject


def _make_player_state(gold: int = 0) -> GameState:
    state = GameState(game_id="t", profile="test", player_id="player")
    state.races["human"] = Race(id="human", name="인간", description="")
    player = Character(
        id="player",
        name="주인공",
        race_id="human",
        gold=gold,
    )
    state.characters[player.id] = player
    state.invalidate_graph()
    return state


def test_to_hero_inventory_includes_gold_zero():
    state = _make_player_state(gold=0)
    payload = to_hero(state)
    inventory = payload["inventory"]
    assert len(inventory) >= 1
    assert inventory[0] == {"name": "금화(0)", "qty": 1}


def test_to_hero_inventory_includes_gold_positive():
    state = _make_player_state(gold=42)
    payload = to_hero(state)
    inventory = payload["inventory"]
    assert inventory[0] == {"name": "금화(42)", "qty": 1}


def test_to_subject_inventory_includes_gold_zero():
    state = _make_player_state(gold=0)
    npc = Character(
        id="npc_test",
        name="테스트 NPC",
        race_id="human",
        gold=0,
    )
    state.characters[npc.id] = npc
    state.active_subject_id = npc.id
    state.invalidate_graph()
    payload = to_subject(state)
    assert payload is not None
    inventory = payload["inventory"]
    assert len(inventory) >= 1
    assert inventory[0] == {"name": "금화(0)", "qty": 1}


def test_to_subject_inventory_includes_gold_positive():
    state = _make_player_state(gold=0)
    npc = Character(
        id="npc_test",
        name="테스트 NPC",
        race_id="human",
        gold=15,
    )
    state.characters[npc.id] = npc
    state.active_subject_id = npc.id
    state.invalidate_graph()
    payload = to_subject(state)
    assert payload is not None
    inventory = payload["inventory"]
    assert inventory[0] == {"name": "금화(15)", "qty": 1}
