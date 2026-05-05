"""Chain skips narrate iff every part is receipt-only and no part is a dramatic
failure. A pass tail or a first-visit move keeps narrate engaged."""

import random
import tempfile

import pytest

from src.domain.entities import (
    Character,
    Connection,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.flow import narrate as narrate_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed(state):
    state.locations["loc_a"] = Location(
        id="loc_a", name="광장", connections=[Connection(target_id="loc_b")]
    )
    state.locations["loc_b"] = Location(id="loc_b", name="시장")
    state.items["sword_01"] = Item(
        id="sword_01",
        name="단검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
    )
    state.items["sword_02"] = Item(
        id="sword_02",
        name="장검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
    )
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="loc_a",
        stats=Stats(),
        hp=10,
        max_hp=20,
        inventory_ids=["sword_01", "sword_02"],
    )
    return state


def _track_narrate(monkeypatch):
    calls: list[dict] = []

    async def fake_run_narrate(*a, **kw):
        calls.append(kw)
        if False:
            yield None

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)
    return calls


async def _collect(it):
    return [ev async for ev in it]


async def _run_chain(state, tmp_saves, monkeypatch, parts, *, player_input="x"):
    narrate_calls = _track_narrate(monkeypatch)

    from src.llm_calls.classify.schema import JudgeOutput

    judge_result = JudgeOutput(actions=list(parts))

    async def fake_judge(*a, **kw):
        return judge_result

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    events = await _collect(
        run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input=player_input,
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
async def test_chain_all_receipts_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed(fresh_state)
    state.characters["player_01"].equipment.weapon = "sword_01"
    events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="transfer", modifiers={
                "from_id": "<self>.equipped.weapon", "to_id": "<self>.inventory",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_02",
            }),
        ],
    )
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("단검" in t and "해제" in t for t in texts), texts
    assert any("장검" in t and "장비" in t for t in texts), texts


@pytest.mark.asyncio
async def test_chain_with_pass_calls_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed(fresh_state)
    _events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="wait"),
        ],
    )
    assert len(narrate_calls) == 1
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("단검" in line and "장비" in line for line in lines), lines


@pytest.mark.asyncio
async def test_chain_first_visit_move_calls_narrate(
    fresh_state, tmp_saves, monkeypatch
):
    state = _seed(fresh_state)
    assert "loc_b" not in state.characters["player_01"].visited_location_ids
    _events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="move", modifiers={"destination": "loc_b"}),
        ],
    )
    assert len(narrate_calls) == 1, narrate_calls
    assert "loc_b" in state.characters["player_01"].visited_location_ids


@pytest.mark.asyncio
async def test_chain_revisit_move_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed(fresh_state)
    state.characters["player_01"].visited_location_ids.add("loc_b")
    _events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="move", modifiers={"destination": "loc_b"}),
        ],
    )
    assert narrate_calls == []


@pytest.mark.asyncio
async def test_chain_with_failed_first_visit_move_skips_narrate(
    fresh_state, tmp_saves, monkeypatch
):
    # Unknown destination -> emit_move "no path" (non-dramatic). Chain stays
    # all-receipt and the failed destination must NOT be marked visited.
    state = _seed(fresh_state)
    assert "loc_unreachable" not in state.characters["player_01"].visited_location_ids
    _events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="move", modifiers={"destination": "loc_unreachable"}),
        ],
    )
    assert narrate_calls == []
    assert "loc_unreachable" not in state.characters["player_01"].visited_location_ids


@pytest.mark.asyncio
async def test_chain_pass_plus_failed_move_drops_failed_act_card(
    fresh_state, tmp_saves, monkeypatch
):
    # [Pass, MoveFail] chain: narrate engages (Pass tail), and the failed
    # MoveAction's act line must be absorbed into narrate prose — NOT
    # surfaced as a system act card. Otherwise the player sees the failure
    # twice (card + narrate body).
    state = _seed(fresh_state)
    events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="wait"),
            Verb(name="move", modifiers={"destination": "loc_unreachable"}),
        ],
    )
    assert len(narrate_calls) == 1, narrate_calls
    # Failed move's humanized line should be in act_log_lines (so narrate sees it),
    # but NOT in the SSE act log_entry stream (would duplicate as a card).
    lines = narrate_calls[0].get("act_log_lines") or []
    assert any("길" in line or "찾지" in line for line in lines), lines
    act_texts = _act_texts(events)
    assert not any("길" in t or "찾지" in t for t in act_texts), act_texts


@pytest.mark.asyncio
async def test_chain_pass_plus_successful_first_visit_move_keeps_card(
    fresh_state, tmp_saves, monkeypatch
):
    # [Pass, MoveSuccess (first visit)] chain: narrate engages, AND the
    # successful move's location-enter act stays as a system card. This is
    # the regression-prevention twin of the failed-move test above.
    state = _seed(fresh_state)
    assert "loc_b" not in state.characters["player_01"].visited_location_ids
    events, narrate_calls = await _run_chain(
        state,
        tmp_saves,
        monkeypatch,
        [
            Verb(name="wait"),
            Verb(name="move", modifiers={"destination": "loc_b"}),
        ],
    )
    assert len(narrate_calls) == 1, narrate_calls
    act_texts = _act_texts(events)
    assert any("시장" in t for t in act_texts), act_texts


def test_chain_with_successful_buy_needs_narrate(fresh_state):
    state = _seed(fresh_state)
    parts = [
        Verb(name="transfer", modifiers={
            "from_id": "m_01", "to_id": "<self>.inventory",
            "mode": "trade", "item_id": "i_01",
        }),
        Verb(name="transfer", modifiers={
            "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
            "mode": "gift", "item_id": "i_01",
        }),
    ]
    assert turn_mod._chain_needs_narrate(state, parts) is True


def test_chain_with_successful_sell_needs_narrate(fresh_state):
    state = _seed(fresh_state)
    parts = [
        Verb(name="transfer", modifiers={
            "from_id": "<self>.inventory", "to_id": "m_01",
            "mode": "trade", "item_id": "i_01",
        }),
        Verb(name="transfer", modifiers={
            "from_id": "<self>.equipped.weapon", "to_id": "<self>.inventory",
            "mode": "gift", "item_id": "i_01",
        }),
    ]
    assert turn_mod._chain_needs_narrate(state, parts) is True


def test_chain_with_successful_give_needs_narrate(fresh_state):
    state = _seed(fresh_state)
    parts = [
        Verb(name="transfer", modifiers={
            "from_id": "<self>.inventory", "to_id": "npc_01",
            "mode": "gift", "item_id": "i_01",
        }),
        Verb(name="transfer", modifiers={
            "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
            "mode": "gift", "item_id": "i_02",
        }),
    ]
    assert turn_mod._chain_needs_narrate(state, parts) is True


def test_chain_with_failed_buy_no_narrate(fresh_state):
    state = _seed(fresh_state)
    parts = [
        Verb(name="transfer", modifiers={
            "from_id": "m_01", "to_id": "<self>.inventory",
            "mode": "trade", "item_id": "i_01",
        }),
        Verb(name="transfer", modifiers={
            "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
            "mode": "gift", "item_id": "i_01",
        }),
    ]
    assert (
        turn_mod._chain_needs_narrate(state, parts, part_failures=[True, False])
        is False
    )
