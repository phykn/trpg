"""Receipt-action policy: equip / unequip / use / buy / sell / give / rest
all skip narrate (no body, no extract) and surface only the engine's act_log."""

import random
import tempfile

import pytest

from src.domain.entities import (
    Character,
    ConsumableEffect,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.flow import narrate as narrate_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import (
    BuyAction,
    EquipAction,
    GiveAction,
    RestAction,
    SellAction,
    UnequipAction,
    UseAction,
)
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed_basic(state, *, with_npc=False):
    state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    state.items["sword_01"] = Item(
        id="sword_01",
        name="단검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
    )
    state.items["potion_01"] = Item(
        id="potion_01",
        name="치유 물약",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
        price=10,
    )
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=20,
        mp=5,
        max_mp=10,
        gold=100,
        inventory_ids=["sword_01", "potion_01"],
    )
    if with_npc:
        state.characters["npc_01"] = Character(
            id="npc_01",
            name="상인",
            race_id="human",
            location_id="plaza_01",
            stats=Stats(),
            hp=10,
            max_hp=10,
            gold=100,
            inventory_ids=["potion_01"],
            relations={"player_01": 80},
        )
    return state


def _track_narrate(monkeypatch):
    """Replace run_narrate with a recorder. Returns the call-list."""
    calls: list[dict] = []

    async def fake_run_narrate(*a, **kw):
        calls.append(kw)
        if False:
            yield None  # async-gen marker

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)
    return calls


async def _collect(it):
    return [ev async for ev in it]


async def _run_with_action(state, tmp_saves, monkeypatch, action, *, client=object()):
    """Stub judge → action; collect events from run_turn."""
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return action

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    events = await _collect(
        run_turn(
            client=client,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="x",
            rng=random.Random(0),
        )
    )
    return events, narrate_calls


def _act_texts(events):
    return [
        ev["data"]["text"]
        for ev in events
        if ev["type"] == "log_entry" and ev["data"].get("kind") == "act"
    ]


@pytest.mark.asyncio
async def test_equip_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    events, narrate_calls = await _run_with_action(
        state, tmp_saves, monkeypatch, EquipAction(action="equip", item_id="sword_01")
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("단검" in t and "장비" in t for t in texts), texts


@pytest.mark.asyncio
async def test_unequip_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    state.characters["player_01"].equipment.weapon = "sword_01"
    events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        UnequipAction(action="unequip", item_id="sword_01"),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("단검" in t and "해제" in t for t in texts), texts


@pytest.mark.asyncio
async def test_use_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    events, narrate_calls = await _run_with_action(
        state, tmp_saves, monkeypatch, UseAction(action="use", item_id="potion_01")
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("물약" in t for t in texts), texts


@pytest.mark.asyncio
async def test_buy_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        BuyAction(action="buy", npc_id="npc_01", item_id="potion_01"),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("샀습니다" in t for t in texts), texts


@pytest.mark.asyncio
async def test_sell_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        SellAction(action="sell", npc_id="npc_01", item_id="potion_01"),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("팔았습니다" in t for t in texts), texts


@pytest.mark.asyncio
async def test_give_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        GiveAction(
            action="give", from_id="player_01", to_id="npc_01", item_id="potion_01"
        ),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("건넸습니다" in t for t in texts), texts


@pytest.mark.asyncio
async def test_rest_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    state.characters["player_01"].hp = 1
    state.characters["player_01"].mp = 1
    # client is an opaque sentinel — rest's narrate path would invoke run_narrate
    # if the receipt policy weren't applied. Mock the summon (encounter) callback
    # to never fire so we hit the rest_completed branch deterministically.
    events, narrate_calls = await _run_with_action(
        state, tmp_saves, monkeypatch, RestAction(action="rest"), client=object()
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("회복" in t for t in texts), texts
