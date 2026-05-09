"""Location-enter system card: every move surfaces the new card text.
First-visit also runs narrate (card stays alongside prose); re-visit is card-only."""

import random
import tempfile

import pytest

from src.game.domain.entities import Character, Connection, Location, Stats
from src.game.flow import narrate as narrate_mod
from src.game.flow import turn as turn_mod
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import JudgeOutput, Verb
from src.llm.calls.narrate import NarrativeFinal
from src.llm.calls.narrate.schema import NarrateOutput
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed(state):
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


def _stub_narrate(monkeypatch):
    """Replace run_narrate with a recorder that emits a tiny final."""
    calls: list[dict] = []

    async def fake_run_narrate(*a, **kw):
        calls.append(kw)
        yield NarrativeFinal(
            body="시장의 풍경이 펼쳐집니다.",
            output=NarrateOutput(turn_summary="시장 둘러봄"),
        )

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)
    return calls


async def _move_to(state, tmp_saves, monkeypatch, dest):
    narrate_calls = _stub_narrate(monkeypatch)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[Verb(name="move", modifiers={"destination": dest})])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    events = [
        ev
        async for ev in run_turn(
            client=object(),
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input=f"{dest}로 이동",
            rng=random.Random(0),
        )
    ]
    return events, narrate_calls


def _act_texts(events):
    return [
        ev["data"]["text"]
        for ev in events
        if ev["type"] == "log_entry" and ev["data"].get("kind") == "act"
    ]


@pytest.mark.asyncio
async def test_first_visit_emits_card_and_runs_narrate(
    fresh_state, tmp_saves, monkeypatch
):
    state = _seed(fresh_state)
    assert "loc_b" not in state.characters["player_01"].visited_location_ids
    events, narrate_calls = await _move_to(state, tmp_saves, monkeypatch, "loc_b")
    # Narrate ran on first visit.
    assert len(narrate_calls) == 1
    # Card text surfaces as an act log entry — visible even though narrate ran.
    texts = _act_texts(events)
    assert any("시장에 도착합니다" in t for t in texts), texts
    # turn_log echo for next-turn engine context.
    assert any("시장 도착" in e.summary for e in state.turn_log), state.turn_log
    # Visit recorded.
    assert "loc_b" in state.characters["player_01"].visited_location_ids


@pytest.mark.asyncio
async def test_revisit_emits_card_and_skips_narrate(
    fresh_state, tmp_saves, monkeypatch
):
    state = _seed(fresh_state)
    state.characters["player_01"].visited_location_ids.add("loc_b")
    events, narrate_calls = await _move_to(state, tmp_saves, monkeypatch, "loc_b")
    # Re-visit: card only, no narrate.
    assert narrate_calls == []
    texts = _act_texts(events)
    assert any("시장에 도착합니다" in t for t in texts), texts
    assert any("시장 도착" in e.summary for e in state.turn_log), state.turn_log


@pytest.mark.asyncio
async def test_failed_move_does_not_emit_arrival_card(
    fresh_state, tmp_saves, monkeypatch
):
    state = _seed(fresh_state)
    events, narrate_calls = await _move_to(
        state, tmp_saves, monkeypatch, "loc_unreachable"
    )
    # No narrate (non-dramatic fail), no arrival card; only the blocked-move line.
    assert narrate_calls == []
    texts = _act_texts(events)
    assert not any("도착합니다" in t for t in texts), texts
