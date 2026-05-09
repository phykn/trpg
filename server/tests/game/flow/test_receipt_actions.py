"""Receipt-action policy: equip / unequip / use / rest skip narrate (no body,
no extract) and surface only the engine's act_log. NPC-touching trades
(buy / sell / give) re-engage narrate so the partner reaction lands; the
engine still emits the act line, narrate absorbs it via `act_log_lines`."""

import random
import tempfile

import pytest

from src.game.domain.entities import (
    Character,
    ConsumableEffect,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.game.flow import narrate as narrate_mod
from src.game.flow import turn as turn_mod
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import Verb
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


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

    # Stage 1b: Verb 인스턴스는 JudgeOutput으로 wrap
    from src.llm.calls.classify.schema import JudgeOutput

    if isinstance(action, Verb):
        action = JudgeOutput(actions=[action])

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
        state,
        tmp_saves,
        monkeypatch,
        Verb(
            name="transfer",
            modifiers={
                "from_id": "<self>.inventory",
                "to_id": "<self>.equipped.weapon",
                "mode": "gift",
                "item_id": "sword_01",
            },
        ),
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
        Verb(
            name="transfer",
            modifiers={
                "from_id": "<self>.equipped.weapon",
                "to_id": "<self>.inventory",
                "mode": "gift",
                "item_id": "sword_01",
            },
        ),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("단검" in t and "해제" in t for t in texts), texts


@pytest.mark.asyncio
async def test_use_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        Verb(name="use", modifiers={"item_id": "potion_01"}),
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("물약" in t for t in texts), texts


@pytest.mark.asyncio
async def test_buy_runs_narrate_with_act_log_line(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    _events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        Verb(
            name="transfer",
            modifiers={
                "from_id": "npc_01",
                "to_id": "player_01",
                "mode": "trade",
                "item_id": "potion_01",
            },
        ),
    )
    assert len(narrate_calls) == 1
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("샀습니다" in line for line in lines), lines


@pytest.mark.asyncio
async def test_sell_runs_narrate_with_act_log_line(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    _events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        Verb(
            name="transfer",
            modifiers={
                "from_id": "player_01",
                "to_id": "npc_01",
                "mode": "trade",
                "item_id": "potion_01",
            },
        ),
    )
    assert len(narrate_calls) == 1
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("팔았습니다" in line for line in lines), lines


@pytest.mark.asyncio
async def test_give_runs_narrate_with_act_log_line(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state, with_npc=True)
    _events, narrate_calls = await _run_with_action(
        state,
        tmp_saves,
        monkeypatch,
        Verb(
            name="transfer",
            modifiers={
                "from_id": "player_01",
                "to_id": "npc_01",
                "mode": "gift",
                "item_id": "potion_01",
            },
        ),
    )
    assert len(narrate_calls) == 1
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("건넸습니다" in line for line in lines), lines


@pytest.mark.asyncio
async def test_rest_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_basic(fresh_state)
    state.characters["player_01"].hp = 1
    state.characters["player_01"].mp = 1
    # client is an opaque sentinel — rest's narrate path would invoke run_narrate
    # if the receipt policy weren't applied. Mock the summon (encounter) callback
    # to never fire so we hit the rest_completed branch deterministically.
    events, narrate_calls = await _run_with_action(
        state, tmp_saves, monkeypatch, Verb(name="rest"), client=object()
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("회복" in t for t in texts), texts
