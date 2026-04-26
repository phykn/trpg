"""§judge equip/unequip — surroundings.equipment 노출 + turn 분기."""
import random
import tempfile

import pytest

from src.domain.entities import (
    ArmorEffect,
    Character,
    Equipment,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.agents.dc_judge.schema import EquipAction, UnequipAction
from src.flow import judge as judge_mod
from src.flow import turn as turn_mod
from src.context import build_surroundings
from src.flow.turn import run_turn


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _judge_returns(monkeypatch, action_obj):
    async def fake_judge(client, state, player_input):
        return action_obj
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)


async def _collect(it):
    return [ev async for ev in it]


def _seed(fresh_state, *, equipped_left=None):
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
        equipment=Equipment(leftHand=equipped_left) if equipped_left else Equipment(),
    )
    fresh_state.characters["player_01"] = p
    fresh_state.items = items
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- surroundings ---------------------------------------------------------


def test_equipment_payload_exposes_id_and_name(fresh_state):
    state = _seed(fresh_state, equipped_left="sword")
    s = build_surroundings(state, "player_01")
    eq = s["equipment"]
    assert eq["leftHand"] == {"id": "sword", "name": "검"}
    assert eq["head"] is None


def test_inventory_kind_distinguishes_weapon_armor(fresh_state):
    state = _seed(fresh_state)
    s = build_surroundings(state, "player_01")
    by_id = {i["id"]: i for i in s["inventory"]}
    assert by_id["sword"]["kind"] == "weapon"
    assert by_id["helm"]["kind"] == "armor"


# --- equip 분기 -----------------------------------------------------------


async def test_equip_weapon_auto_picks_empty_hand(fresh_state, tmp_data, monkeypatch):
    state = _seed(fresh_state)
    _judge_returns(monkeypatch, EquipAction(action="equip", item_id="sword"))
    events = await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="검을 든다",
            rng=random.Random(0),
        )
    )
    assert events[-1]["type"] == "done"
    p = state.characters["player_01"]
    assert p.equipment.leftHand == "sword"  # 첫 빈 손
    assert state.turn_count == 1


async def test_equip_armor_picks_first_empty_slot(fresh_state, tmp_data, monkeypatch):
    state = _seed(fresh_state)
    _judge_returns(monkeypatch, EquipAction(action="equip", item_id="helm"))
    await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="투구를 쓴다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.equipment.head == "helm"


# --- unequip 분기 ---------------------------------------------------------


async def test_unequip_finds_slot_by_item(fresh_state, tmp_data, monkeypatch):
    state = _seed(fresh_state, equipped_left="sword")
    _judge_returns(monkeypatch, UnequipAction(action="unequip", item_id="sword"))
    await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="검을 칼집에 넣는다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.equipment.leftHand is None
    # 인벤토리에는 그대로
    assert "sword" in p.inventory_ids
