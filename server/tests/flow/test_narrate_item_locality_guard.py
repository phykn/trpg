"""Test that narrate's apply_changes + enforce_item_locality wire correctly."""

from src.domain.entities import Character, Item, Location, Race, Stats
from src.domain.state import GameState
from src.engines.invariants import enforce_item_locality


def _state() -> GameState:
    s = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    s.races["race_human"] = Race(id="race_human", name="인간", description="인간 종족")
    s.locations["loc_01"] = Location(id="loc_01", name="광장")
    s.items["sword_01"] = Item(id="sword_01", name="검", weight=1, price=10)
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        is_player=True,
    )
    p.max_hp = p.hp = 20
    p.max_mp = p.mp = 10
    s.characters["player_01"] = p
    npc = Character(
        id="z_npc_01",
        name="상인",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
    )
    npc.max_hp = npc.hp = 20
    npc.max_mp = npc.mp = 10
    s.characters["z_npc_01"] = npc
    return s


def test_enforce_after_simulated_llm_duplicate_set():
    """Simulate LLM-emitted state_changes that result in duplication; enforcer cleans up."""
    state = _state()
    # Simulate the bug: player got the sword, but NPC equipment still references it.
    state.characters["player_01"].inventory_ids.append("sword_01")
    state.characters["z_npc_01"].equipment.weapon = "sword_01"

    dirty: set[tuple[str, str]] = set()
    warnings = enforce_item_locality(state, dirty=dirty)

    assert len(warnings) == 1
    # Player keeps it (player_01 < z_npc_01 alphabetically).
    assert "sword_01" in state.characters["player_01"].inventory_ids
    assert state.characters["z_npc_01"].equipment.weapon is None
    assert ("characters", "z_npc_01") in dirty
