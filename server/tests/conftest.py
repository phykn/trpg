import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _clear_save_locks():
    """Clear the global save locks dict between tests to avoid event loop binding issues."""
    from src.db import store

    store._save_locks.clear()
    yield
    store._save_locks.clear()


@pytest.fixture
def fresh_state():
    from src.game.domain.state import GameState

    return GameState(
        game_id="t",
        profile="default",
        player_id="player_01",
    )


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def collect():
    async def _c(it):
        return [ev async for ev in it]

    return _c


@pytest.fixture
def judge_returns(monkeypatch):
    """Stub run_judge across the 3 entry points; optionally stub run_narrate.

    Single-action paths invoke narrate (engine notices get absorbed into
    prose). For LLM-free engine tests, default stub_narrate=True replaces it
    with an empty async-gen so no real model is reached. Tests that exercise
    narrate output directly should pass stub_narrate=False.
    """

    def _stub(action_obj, *, stub_narrate=True):
        from src.game.flow import combat_phase as combat_phase_mod
        from src.game.flow import judge as judge_mod
        from src.game.flow import turn as turn_mod

        # Wrap a Verb or list[Verb] into a JudgeOutput so verb-direct dispatch sees the right type.
        from src.llm.calls.classify.schema import JudgeOutput, Verb

        if isinstance(action_obj, Verb):
            action_obj = JudgeOutput(actions=[action_obj])
        elif isinstance(action_obj, list) and all(
            isinstance(v, Verb) for v in action_obj
        ):
            action_obj = JudgeOutput(actions=action_obj)

        async def fake_judge(*a, **kw):
            return action_obj

        for mod in (judge_mod, turn_mod, combat_phase_mod):
            monkeypatch.setattr(mod, "run_judge", fake_judge)

        if stub_narrate:
            from src.game.flow import narrate as narrate_mod

            async def _noop_narrate(*a, **kw):
                if False:
                    yield None  # async-gen marker

            monkeypatch.setattr(narrate_mod, "run_narrate", _noop_narrate)

    return _stub
