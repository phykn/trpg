"""§judge use action — surroundings exposure + out-of-combat / combat turn branching."""

import random

from src.domain.entities import (
    Character,
    CombatBehavior,
    ConsumableEffect,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.llm_calls.dc_judge.schema import UseAction
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.context import build_surroundings
from src.flow.turn import run_turn


def _seed(fresh_state, *, give_potion=True, give_sword=False, hp=10):
    items: dict[str, Item] = {}
    inv: list[str] = []
    if give_potion:
        items["potion"] = Item(
            id="potion",
            name="치유 물약",
            consumable=True,
            effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
        )
        inv.append("potion")
    if give_sword:
        items["sword"] = Item(
            id="sword",
            name="검",
            effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
        )
        inv.append("sword")
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        hp=hp,
        max_hp=20,
        location_id="plaza_01",
        inventory_ids=inv,
    )
    fresh_state.characters["player_01"] = p
    fresh_state.items = items
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- surroundings ---------------------------------------------------------


def test_inventory_lists_consumable_items(fresh_state):
    state = _seed(fresh_state, give_potion=True)
    s = build_surroundings(state, "player_01")
    assert "inventory" in s
    inv = s["inventory"]
    assert len(inv) == 1
    assert inv[0]["id"] == "potion"
    assert inv[0]["kind"] == "consumable"


def test_inventory_marks_weapons_as_equip_kind(fresh_state):
    state = _seed(fresh_state, give_potion=False, give_sword=True)
    s = build_surroundings(state, "player_01")
    assert len(s["inventory"]) == 1
    assert s["inventory"][0]["kind"] == "weapon"
    # weapons should match equip, not use


def test_inventory_dedupes_duplicates(fresh_state):
    """Duplicate item ids in inventory_ids collapse to a single payload entry —
    surroundings.inventory dedupes via the seen-set in `_inventory_payload`."""
    state = _seed(fresh_state, give_potion=True)
    state.characters["player_01"].inventory_ids.append("potion")
    s = build_surroundings(state, "player_01")
    inv = s["inventory"]
    assert len(inv) == 1
    assert inv[0]["id"] == "potion"


def test_inventory_includes_quest_key_with_on_use(fresh_state):
    state = _seed(fresh_state, give_potion=False)
    state.items["quest_key"] = Item(
        id="quest_key", name="고대의 열쇠", on_use="open_door"
    )
    state.characters["player_01"].inventory_ids = ["quest_key"]
    s = build_surroundings(state, "player_01")
    assert any(i["id"] == "quest_key" for i in s["inventory"])


# --- Out-of-combat use branch ---------------------------------------------


async def test_use_action_consumes_item_and_heals(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed(fresh_state, hp=10)
    judge_returns(UseAction(action="use", item_id="potion"))
    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="물약을 마신다",
            rng=random.Random(0),
        )
    )
    assert events[-1]["type"] == "done"
    assert state.characters["player_01"].hp == 18  # heal 8
    # consumable=True so it is decremented from inventory
    assert state.characters["player_01"].inventory_ids == []
    assert state.turn_count == 1


# --- In-combat use branch -------------------------------------------------


async def test_combat_use_consumes_player_turn(
    fresh_state, tmp_data, judge_returns, collect
):
    from src.engines import combat as combat_engine

    state = _seed(fresh_state, hp=5)
    state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=10,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    combat_engine.start_combat(state, ["goblin_01"], rng=random.Random(0))
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    judge_returns(UseAction(action="use", item_id="potion"))
    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="물약 마심",
            rng=random.Random(0),
        )
    )
    use_evs = [
        e
        for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "use"
    ]
    assert use_evs
    # Auto-cycle ran to terminal outcome → combat_state cleared.
    assert state.combat_state is None
    # Potion consumed (heal effect applied even though NPC kept hitting back).
    assert "potion" not in state.characters["player_01"].inventory_ids
