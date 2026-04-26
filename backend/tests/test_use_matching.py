"""§judge use action — surroundings 노출 + 평시·전투 turn 분기."""
import random
import tempfile

import pytest

from src.domain.entities import (
    Character,
    CombatBehavior,
    ConsumableEffect,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.llm_client.agents.dc_judge.schema import UseAction
from src.pipeline import judge as judge_mod
from src.pipeline import turn as turn_mod
from src.pipeline.context import build_surroundings
from src.pipeline.turn import run_turn


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
    assert inv[0]["effect"] == "heal"


def test_inventory_marks_weapons_as_equip_kind(fresh_state):
    state = _seed(fresh_state, give_potion=False, give_sword=True)
    s = build_surroundings(state, "player_01")
    assert len(s["inventory"]) == 1
    assert s["inventory"][0]["kind"] == "weapon"
    # weapon 은 use 가 아니라 equip 매칭으로 가야 함


def test_inventory_groups_qty(fresh_state):
    state = _seed(fresh_state, give_potion=True)
    state.characters["player_01"].inventory_ids.append("potion")
    s = build_surroundings(state, "player_01")
    inv = s["inventory"]
    assert inv[0]["qty"] == 2


def test_inventory_includes_quest_key_with_on_use(fresh_state):
    state = _seed(fresh_state, give_potion=False)
    state.items["quest_key"] = Item(
        id="quest_key", name="고대의 열쇠", on_use="open_door"
    )
    state.characters["player_01"].inventory_ids = ["quest_key"]
    s = build_surroundings(state, "player_01")
    assert any(i["id"] == "quest_key" for i in s["inventory"])


# --- 평시 use 분기 --------------------------------------------------------


async def test_use_action_consumes_item_and_heals(fresh_state, tmp_data, monkeypatch):
    state = _seed(fresh_state, hp=10)
    _judge_returns(monkeypatch, UseAction(action="use", item_id="potion"))
    events = await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="물약을 마신다",
            rng=random.Random(0),
        )
    )
    assert events[-1]["type"] == "done"
    assert state.characters["player_01"].hp == 18  # heal 8
    # consumable=True 라 인벤에서 차감
    assert state.characters["player_01"].inventory_ids == []
    assert state.turn_count == 1


# --- 전투 중 use 분기 -----------------------------------------------------


async def test_combat_use_consumes_player_turn(fresh_state, tmp_data, monkeypatch):
    from src.pipeline import combat as combat_engine

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

    _judge_returns(monkeypatch, UseAction(action="use", item_id="potion"))
    events = await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="물약 마심",
            rng=random.Random(0),
        )
    )
    types = [e["type"] for e in events]
    use_evs = [
        e for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "use"
    ]
    assert use_evs
    # 회복 적용 + 인벤 차감
    assert state.characters["player_01"].hp >= 5  # 그리고 npc 가 깎을 수도 있음
    assert "potion" not in state.characters["player_01"].inventory_ids
