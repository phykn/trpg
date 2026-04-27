"""run_turn must reject input when the player is dead — no judge call, no narrate, no use/equip/etc."""
import tempfile

import pytest

from src.domain.entities import Character, Stats
from src.flow import judge as judge_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def dead_player_state(fresh_state):
    player = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=0,
        max_hp=20,
        alive=False,
    )
    fresh_state.characters["player_01"] = player
    return fresh_state


async def _collect(it):
    return [ev async for ev in it]


async def test_dead_player_turn_short_circuits(dead_player_state, tmp_data, monkeypatch):
    judge_called = False

    async def fake_judge(*a, **kw):
        nonlocal judge_called
        judge_called = True
        raise AssertionError("judge must not run when player is dead")
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    events = await _collect(
        run_turn(
            client=None,
            state=dead_player_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="회복약을 마신다",
        )
    )

    assert not judge_called
    types = [e["type"] for e in events]
    assert "judge" not in types
    act_logs = [e for e in events if e["type"] == "log_entry" and e["data"].get("kind") == "act"]
    assert any("쓰러진" in e["data"]["text"] for e in act_logs)
