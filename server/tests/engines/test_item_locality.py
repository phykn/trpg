"""Tests for runtime item-locality invariant.

A given item_id may appear in at most one location:
- a single character's inventory_ids
- a single character's equipment slot
- a single location's item_ids

Any other configuration is a duplication bug (LLM-emitted state_change went wrong).
"""

from src.domain.entities import Character, Item, Location, Race, Stats
from src.domain.state import GameState
from src.engines.invariants import check_item_locality, enforce_item_locality


def _state_with_item(item_id: str = "sword_01") -> GameState:
    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    state.races["race_human"] = Race(
        id="race_human", name="인간", description="인간 종족"
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.items[item_id] = Item(id=item_id, name="검", weight=1, price=10)
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
    state.characters["player_01"] = p
    return state


def _add_npc(state: GameState, npc_id: str = "npc_01") -> Character:
    npc = Character(
        id=npc_id,
        name="NPC",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
    )
    npc.max_hp = npc.hp = 20
    npc.max_mp = npc.mp = 10
    state.characters[npc_id] = npc
    return npc


# ----- check_item_locality (read-only detection) -----


def test_check_item_locality_clean_state():
    state = _state_with_item()
    state.characters["player_01"].inventory_ids.append("sword_01")
    assert check_item_locality(state) == []


def test_check_item_locality_two_inventories():
    state = _state_with_item()
    npc = _add_npc(state)
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.inventory_ids.append("sword_01")
    violations = check_item_locality(state)
    assert len(violations) == 1
    assert "sword_01" in violations[0]


def test_check_item_locality_inventory_plus_other_char_equipment():
    state = _state_with_item()
    npc = _add_npc(state)
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.equipment.weapon = "sword_01"
    violations = check_item_locality(state)
    assert len(violations) == 1
    assert "sword_01" in violations[0]


def test_check_item_locality_inventory_plus_own_equipment_is_ok():
    """An item equipped by its own owner counts as one location (not duplication)."""
    state = _state_with_item()
    state.characters["player_01"].inventory_ids.append("sword_01")
    state.characters["player_01"].equipment.weapon = "sword_01"
    assert check_item_locality(state) == []


def test_check_item_locality_inventory_plus_location_items():
    state = _state_with_item()
    state.characters["player_01"].inventory_ids.append("sword_01")
    state.locations["loc_01"].item_ids.append("sword_01")
    violations = check_item_locality(state)
    assert len(violations) == 1


def test_check_item_locality_three_way_duplication():
    state = _state_with_item()
    npc = _add_npc(state)
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.inventory_ids.append("sword_01")
    state.locations["loc_01"].item_ids.append("sword_01")
    violations = check_item_locality(state)
    assert len(violations) == 1
    # The message should mention all three locations.
    msg = violations[0]
    assert "player_01" in msg
    assert "npc_01" in msg
    assert "loc_01" in msg


# ----- enforce_item_locality (detect + auto-repair) -----


def test_enforce_item_locality_clean_state_returns_empty():
    state = _state_with_item()
    state.characters["player_01"].inventory_ids.append("sword_01")
    warnings = enforce_item_locality(state)
    assert warnings == []
    # No state change.
    assert state.characters["player_01"].inventory_ids == ["sword_01"]


def test_enforce_item_locality_two_inventories_keeps_first_clears_rest():
    """Deterministic repair: keep the alphabetically-first location, clear others."""
    state = _state_with_item()
    npc = _add_npc(state, "z_npc")  # alphabetically after player_01
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.inventory_ids.append("sword_01")
    warnings = enforce_item_locality(state)
    assert len(warnings) == 1
    assert "sword_01" in warnings[0] or "검" in warnings[0]
    # Player keeps it (player_01 < z_npc alphabetically).
    assert "sword_01" in state.characters["player_01"].inventory_ids
    assert "sword_01" not in state.characters["z_npc"].inventory_ids


def test_enforce_item_locality_inventory_plus_other_equipment_keeps_first():
    state = _state_with_item()
    npc = _add_npc(state, "z_npc")
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.equipment.weapon = "sword_01"
    warnings = enforce_item_locality(state)
    assert len(warnings) == 1
    # Player keeps it; NPC's equipment slot cleared.
    assert "sword_01" in state.characters["player_01"].inventory_ids
    assert state.characters["z_npc"].equipment.weapon is None


def test_enforce_item_locality_marks_dirty_for_modified_entities():
    """When repair touches a character or location, mark it dirty so persistence picks it up."""
    state = _state_with_item()
    npc = _add_npc(state, "z_npc")
    state.characters["player_01"].inventory_ids.append("sword_01")
    npc.inventory_ids.append("sword_01")
    dirty: set[tuple[str, str]] = set()
    enforce_item_locality(state, dirty=dirty)
    assert ("characters", "z_npc") in dirty
