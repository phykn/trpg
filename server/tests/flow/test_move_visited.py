"""Move first-visit triggers narrate; re-visit is receipt-only.

Visit tracking lives on `Character.visited_location_ids`. New games start with
an empty set, so every fresh location narrates once; subsequent moves to the
same place skip narrate."""

import random
import tempfile

import pytest

from src.domain.entities import Character, Connection, Location, Stats
from src.flow import narrate as narrate_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import JudgeOutput, Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed_two_locations(state):
    state.locations["loc_a"] = Location(
        id="loc_a", name="광장", connections=[Connection(target_id="loc_b")]
    )
    state.locations["loc_b"] = Location(
        id="loc_b", name="시장", connections=[Connection(target_id="loc_a")]
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


async def _move_to(state, tmp_saves, monkeypatch, dest):
    narrate_calls = _track_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[Verb(name="move", modifiers={"destination": dest})])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    events = await _collect(
        run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input=f"{dest}로 이동",
            rng=random.Random(0),
        )
    )
    return events, narrate_calls


@pytest.mark.asyncio
async def test_move_first_visit_calls_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_two_locations(fresh_state)
    assert "loc_b" not in state.characters["player_01"].visited_location_ids
    _events, narrate_calls = await _move_to(state, tmp_saves, monkeypatch, "loc_b")
    assert len(narrate_calls) == 1, narrate_calls
    # Visit recorded so the next move would be a receipt.
    assert "loc_b" in state.characters["player_01"].visited_location_ids


@pytest.mark.asyncio
async def test_move_revisit_skips_narrate(fresh_state, tmp_saves, monkeypatch):
    state = _seed_two_locations(fresh_state)
    state.characters["player_01"].visited_location_ids.add("loc_b")
    _events, narrate_calls = await _move_to(state, tmp_saves, monkeypatch, "loc_b")
    assert narrate_calls == []
    # Idempotent: still in the set.
    assert "loc_b" in state.characters["player_01"].visited_location_ids


@pytest.mark.asyncio
async def test_failed_move_does_not_mark_visited_or_call_narrate(
    fresh_state, tmp_saves, monkeypatch
):
    # Unknown destination triggers emit_move's "no path" branch (non-dramatic fail).
    state = _seed_two_locations(fresh_state)
    assert "loc_unreachable" not in state.characters["player_01"].visited_location_ids
    _events, narrate_calls = await _move_to(
        state, tmp_saves, monkeypatch, "loc_unreachable"
    )
    assert narrate_calls == []
    assert "loc_unreachable" not in state.characters["player_01"].visited_location_ids
