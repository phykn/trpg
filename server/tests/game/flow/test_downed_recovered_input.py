"""When previous_phase_signal == 'downed_recovered', the post-combat
aftermath narrate must run with empty history + empty player_view memories.
Otherwise the LLM pulls stale events (e.g. "100골드 발견") into the
recovery beat. The signal-driven pruning is the only mechanism the prompt
has to enforce a clean recovery scene."""

import pytest

from src.game.domain.entities import Character, Location, Stats
from src.game.domain.memory import Memory, TurnLogEntry
from src.game.flow import narrate as narrate_mod
from src.game.flow.narrate import run_narrate
from src.db.local_fs import LocalFsScenarioRepo


@pytest.fixture
def state_with_strong_history(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        memories=[
            Memory(content="100골드를 발견함", importance=3, turn=1),
            Memory(content="장로의 단검을 받음", importance=2, turn=2),
        ],
    )
    fresh_state.turn_log.append(
        TurnLogEntry(turn=1, target=None, summary="100골드를 발견함")
    )
    fresh_state.turn_log.append(
        TurnLogEntry(turn=2, target=None, summary="장로와 대화함")
    )
    return fresh_state


async def _drain(stream):
    async for _ in stream:
        pass


async def _stub_world(monkeypatch):
    async def fake_world(scenario_repo, profile, missing_ok=False):
        return ""

    monkeypatch.setattr(narrate_mod, "build_world_layer", fake_world)


async def test_recovery_signal_zeroes_history_and_memories(
    state_with_strong_history, monkeypatch
):
    captured: dict = {}

    async def fake_stream_narrate(client, input_, locale="ko"):
        captured["input"] = input_
        if False:
            yield None  # async-gen marker

    monkeypatch.setattr(narrate_mod, "stream_narrate", fake_stream_narrate)
    await _stub_world(monkeypatch)

    graph = state_with_strong_history.graph()
    await _drain(
        run_narrate(
            client=None,
            state=state_with_strong_history,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            player_input="",
            judge_result={"action": "pass"},
            graph=graph,
            previous_phase_signal="downed_recovered",
        )
    )

    input_ = captured["input"]
    assert input_.history == "", "recovery beat must not surface prior turn_log"
    assert input_.player_view.get("memories") == [], (
        "recovery beat must not surface prior player memories"
    )


async def test_no_signal_keeps_history_and_default_player_view(
    state_with_strong_history, monkeypatch
):
    """Sanity: without the signal, history is non-empty and player_view
    follows build_player_view defaults (no 'memories' key forced in)."""
    captured: dict = {}

    async def fake_stream_narrate(client, input_, locale="ko"):
        captured["input"] = input_
        if False:
            yield None

    monkeypatch.setattr(narrate_mod, "stream_narrate", fake_stream_narrate)
    await _stub_world(monkeypatch)

    graph = state_with_strong_history.graph()
    await _drain(
        run_narrate(
            client=None,
            state=state_with_strong_history,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            player_input="",
            judge_result={"action": "pass"},
            graph=graph,
            previous_phase_signal=None,
        )
    )

    input_ = captured["input"]
    assert input_.history != "", "non-recovery turn keeps the history layer"
    # build_player_view doesn't include memories today; recovery branch is the only place that injects the key.
    assert "memories" not in input_.player_view
