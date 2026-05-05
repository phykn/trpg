"""§judge equip/unequip — surroundings.equipment exposure + turn branching."""

import random

from src.domain.entities import (
    ArmorEffect,
    Character,
    Equipment,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.llm_calls.classify.schema import Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.context import build_surroundings
from src.flow.turn import run_turn


def _seed(fresh_state, *, equipped_weapon=None):
    items = {
        "sword": Item(
            id="sword",
            name="검",
            effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
        ),
        "helm": Item(
            id="helm",
            name="투구",
            effects=ArmorEffect(type="armor", defense=2),
        ),
    }
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="plaza_01",
        inventory_ids=["sword", "helm"],
        equipment=Equipment(weapon=equipped_weapon) if equipped_weapon else Equipment(),
    )
    fresh_state.characters["player_01"] = p
    fresh_state.items = items
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- surroundings ---------------------------------------------------------


def test_equipment_payload_exposes_id_and_name(fresh_state):
    state = _seed(fresh_state, equipped_weapon="sword")
    s = build_surroundings(state, "player_01")
    eq = s["equipment"]
    assert eq["weapon"] == {"id": "sword", "name": "검"}
    assert eq["armor"] is None


def test_inventory_kind_distinguishes_weapon_armor(fresh_state):
    state = _seed(fresh_state)
    s = build_surroundings(state, "player_01")
    by_id = {i["id"]: i for i in s["inventory"]}
    assert by_id["sword"]["kind"] == "weapon"
    assert by_id["helm"]["kind"] == "armor"


# --- equip branch ---------------------------------------------------------


async def test_equip_weapon_lands_in_weapon_slot(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed(fresh_state)
    judge_returns(Verb(name="transfer", modifiers={
        "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
        "mode": "gift", "item_id": "sword",
    }))
    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="검을 든다",
            rng=random.Random(0),
        )
    )
    assert events[-1]["type"] == "done"
    p = state.characters["player_01"]
    assert p.equipment.weapon == "sword"
    assert state.turn_count == 1


async def test_equip_armor_picks_armor_slot_first(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed(fresh_state)
    judge_returns(Verb(name="transfer", modifiers={
        "from_id": "<self>.inventory", "to_id": "<self>.equipped.armor",
        "mode": "gift", "item_id": "helm",
    }))
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="투구를 쓴다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.equipment.armor == "helm"


# --- unequip branch -------------------------------------------------------


async def test_unequip_finds_slot_by_item(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed(fresh_state, equipped_weapon="sword")
    judge_returns(Verb(name="transfer", modifiers={
        "from_id": "<self>.equipped.weapon", "to_id": "<self>.inventory",
        "mode": "gift", "item_id": "sword",
    }))
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="검을 칼집에 넣는다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.equipment.weapon is None
    # still in inventory
    assert "sword" in p.inventory_ids
