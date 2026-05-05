"""Combat outcome `downed` (auto death-save resolved to stable) sets a
one-shot signal so the *next* /turn's narrate opens with recovery prose.
The signal is consumed at narrate-call time and cleared on the way through
turn entry, so it can't echo across multiple turns or leak into the combat
re-entry path.
"""

import tempfile

import pytest

from src.llm_calls.classify.schema import JudgeOutput, Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.domain.entities import Character, Location, Stats
from src.flow import narrate as narrate_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def state_with_signal(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
    )
    fresh_state.previous_phase_signal = "downed_recovered"
    return fresh_state


async def _collect(it):
    return [ev async for ev in it]


async def test_signal_passed_to_narrate_and_cleared(
    state_with_signal,
    tmp_saves,
    monkeypatch,
):
    """A turn that enters narrate (judge=pass) hands the signal to run_narrate
    via kwargs, then state.previous_phase_signal returns to None — one-shot."""
    captured_kw: dict = {}

    async def fake_run_narrate(*a, **kw):
        captured_kw.update(kw)
        if False:
            yield None  # pragma: no cover

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[Verb(name="wait")])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_with_signal,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="둘러본다",
        )
    )

    assert captured_kw.get("previous_phase_signal") == "downed_recovered"
    assert state_with_signal.previous_phase_signal is None, (
        "signal must clear after one consume"
    )


async def test_signal_cleared_even_when_combat_branch_runs(
    state_with_signal,
    tmp_saves,
    monkeypatch,
):
    """Combat re-entry doesn't call run_narrate (combat_narrate handles the
    opening), but the signal must still clear at turn entry — otherwise it
    leaks into a later non-combat turn that wasn't 'just-recovered'."""
    from src.domain.state import CombatState

    state_with_signal.combat_state = CombatState(
        turn_order=["player_01"], enemy_ids=[], round=1
    )

    async def fake_run_combat_player_turn(*a, **kw):
        if False:
            yield None  # pragma: no cover

    monkeypatch.setattr(turn_mod, "run_combat_player_turn", fake_run_combat_player_turn)

    await _collect(
        run_turn(
            client=None,
            state=state_with_signal,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="공격",
        )
    )

    assert state_with_signal.previous_phase_signal is None, (
        "combat re-entry must still clear the signal at turn entry"
    )


async def test_no_signal_passes_none(
    fresh_state,
    tmp_saves,
    monkeypatch,
):
    """When state.previous_phase_signal is None (the common case), narrate
    receives None — not the empty string, not a missing kwarg."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
    )

    captured_kw: dict = {}

    async def fake_run_narrate(*a, **kw):
        captured_kw.update(kw)
        if False:
            yield None  # pragma: no cover

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[Verb(name="wait")])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=fresh_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="둘러본다",
        )
    )

    assert captured_kw.get("previous_phase_signal") is None
