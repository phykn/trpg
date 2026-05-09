"""Narrate is called only when an engine error matches _DRAMATIC_FAIL_KEYS.

Receipt actions failing on a non-dramatic key (e.g. "item not in inventory")
surface the humanized act line and stop. Failures matching the dramatic keys
(affinity / required stats / npc gold) escalate back to a narrate round so the
player gets a GM reaction."""

import random
import tempfile

import pytest

from src.game.domain.entities import (
    Character,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.game.flow import narrate as narrate_mod
from src.game.flow import turn as turn_mod
from src.game.flow.error_phrases import is_dramatic_fail
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import JudgeOutput, Verb
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_dramatic_keys_match():
    class E(Exception):
        pass

    assert is_dramatic_fail(E("affinity too low to trade with X"))
    assert is_dramatic_fail(E("required stats not met for spell"))
    assert is_dramatic_fail(E("npc has not enough gold"))
    assert not is_dramatic_fail(E("item not in inventory"))
    assert not is_dramatic_fail(E("hp already full"))
    assert not is_dramatic_fail(E("not enough gold"))  # player gold, not NPC's


def test_dramatic_keys_match_strings():
    assert is_dramatic_fail("AFFINITY TOO LOW TO TRADE")
    assert not is_dramatic_fail("not enough gold")


async def _collect(it):
    return [ev async for ev in it]


def _track_narrate(monkeypatch):
    calls: list[dict] = []

    async def fake_run_narrate(*a, **kw):
        calls.append(kw)
        if False:
            yield None

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)
    return calls


def _seed_trade(fresh_state, *, npc_affinity=80, npc_gold=100):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.items["potion_01"] = Item(
        id="potion_01", name="치유 물약", consumable=False, price=10
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=20,
        gold=100,
        inventory_ids=["potion_01"],
    )
    fresh_state.characters["npc_01"] = Character(
        id="npc_01",
        name="상인",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=10,
        gold=npc_gold,
        inventory_ids=["potion_01"],
        relations={"player_01": npc_affinity},
    )
    return fresh_state


@pytest.mark.asyncio
async def test_buy_dramatic_fail_calls_narrate(fresh_state, tmp_saves, monkeypatch):
    """Affinity below trade_threshold raises 'affinity too low to trade' →
    narrate engages."""
    state = _seed_trade(fresh_state, npc_affinity=-100)
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(
            actions=[
                Verb(
                    name="transfer",
                    modifiers={
                        "from_id": "npc_01",
                        "to_id": "player_01",
                        "mode": "trade",
                        "item_id": "potion_01",
                    },
                )
            ]
        )

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    await _collect(
        run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="물약을 산다",
            rng=random.Random(0),
        )
    )
    assert len(narrate_calls) == 1, narrate_calls
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("거래" in line for line in lines), lines


@pytest.mark.asyncio
async def test_sell_npc_no_gold_calls_narrate(fresh_state, tmp_saves, monkeypatch):
    """Sell-side dramatic key 'npc has not enough gold' engages narrate."""
    state = _seed_trade(fresh_state, npc_affinity=80, npc_gold=0)
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(
            actions=[
                Verb(
                    name="transfer",
                    modifiers={
                        "from_id": "player_01",
                        "to_id": "npc_01",
                        "mode": "trade",
                        "item_id": "potion_01",
                    },
                )
            ]
        )

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    await _collect(
        run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="물약을 판다",
            rng=random.Random(0),
        )
    )
    assert len(narrate_calls) == 1, narrate_calls


@pytest.mark.asyncio
async def test_buy_nondramatic_fail_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    """'NPC has no such item' is not a dramatic key — receipt only, no narrate."""
    state = _seed_trade(fresh_state, npc_affinity=80)
    # Strip the item from the NPC; affinity is fine.
    state.characters["npc_01"].inventory_ids = []
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(
            actions=[
                Verb(
                    name="transfer",
                    modifiers={
                        "from_id": "npc_01",
                        "to_id": "player_01",
                        "mode": "trade",
                        "item_id": "potion_01",
                    },
                )
            ]
        )

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    events = await _collect(
        run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="물약을 산다",
            rng=random.Random(0),
        )
    )
    assert narrate_calls == []
    # The humanized fail line should reach the player as a regular act log.
    act_texts = [
        ev["data"]["text"]
        for ev in events
        if ev["type"] == "log_entry" and ev["data"].get("kind") == "act"
    ]
    assert any("물건" in t or "거래" in t for t in act_texts), act_texts


@pytest.mark.asyncio
async def test_equip_required_stats_calls_narrate(fresh_state, tmp_saves, monkeypatch):
    """Equipping with missing stats raises 'required stats not met' → narrate."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.items["heavy_sword"] = Item(
        id="heavy_sword",
        name="대검",
        effects=WeaponEffect(type="weapon", weapon_dice="2d8"),
        required=Stats(STR=20, DEX=20, CON=20, INT=20, WIS=20, CHA=20),
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),  # default 10 across the board — way below 20
        hp=10,
        max_hp=20,
        inventory_ids=["heavy_sword"],
    )
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(
            actions=[
                Verb(
                    name="transfer",
                    modifiers={
                        "from_id": "<self>.inventory",
                        "to_id": "<self>.equipped.weapon",
                        "mode": "gift",
                        "item_id": "heavy_sword",
                    },
                )
            ]
        )

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    await _collect(
        run_turn(
            client=object(),
            state=fresh_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="대검을 든다",
            rng=random.Random(0),
        )
    )
    assert len(narrate_calls) == 1, narrate_calls
