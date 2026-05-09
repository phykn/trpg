"""quest_action turns must create confirmation without calling the judge LLM.

Quest accept/abandon used to mutate immediately. The current contract
requires an explicit confirmation step first, so the button turn stores
pending_confirmation and leaves quest status unchanged.
"""

import tempfile

import pytest

from src.game.domain.entities import Character, Location, Quest, Stats
from src.game.flow import turn as turn_mod
from src.game.flow.turn import run_turn
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.llm.calls.classify.schema import JudgeOutput, Verb


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def state_with_pending_quest(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        max_hp=20,
        hp=20,
    )
    fresh_state.characters["giver_01"] = Character(
        id="giver_01",
        name="의뢰인",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(),
    )
    fresh_state.quests["q1"] = Quest(
        id="q1",
        title="첫 의뢰",
        summary="x",
        giver_id="giver_01",
        difficulty="normal",
        status="pending",
        requires_acceptance=True,
    )
    return fresh_state


async def _collect(it):
    return [ev async for ev in it]


async def test_button_only_accept_skips_judge(
    state_with_pending_quest,
    tmp_saves,
    monkeypatch,
):
    """quest_action=('accept', qid) creates confirmation and skips judge."""
    judge_calls: list = []

    async def fake_judge(*a, **kw):
        judge_calls.append((a, kw))
        return JudgeOutput(actions=[Verb(name="wait")])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    events = await _collect(
        run_turn(
            client=None,
            state=state_with_pending_quest,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="",
            quest_action=("accept", "q1"),
        )
    )

    assert state_with_pending_quest.quests["q1"].status == "pending"
    assert state_with_pending_quest.pending_confirmation["kind"] == "quest_accept"
    assert judge_calls == []
    assert any(ev.get("type") == "confirmation_required" for ev in events)
    assert events[-1] == {"type": "done", "data": {}}


async def test_button_only_abandon_skips_judge(
    state_with_pending_quest,
    tmp_saves,
    monkeypatch,
):
    """abandon variant creates confirmation and skips judge."""
    state_with_pending_quest.quests["q1"].status = "active"
    judge_calls: list = []

    async def fake_judge(*a, **kw):
        judge_calls.append((a, kw))
        return JudgeOutput(actions=[Verb(name="wait")])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_with_pending_quest,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="",
            quest_action=("abandon", "q1"),
        )
    )

    assert state_with_pending_quest.quests["q1"].status == "active"
    assert state_with_pending_quest.pending_confirmation["kind"] == "quest_abandon"
    assert judge_calls == []


async def test_quest_action_with_player_input_still_calls_judge(
    state_with_pending_quest,
    tmp_saves,
    monkeypatch,
):
    """quest_action + non-empty player_input still creates confirmation first."""
    judge_calls: list = []

    async def fake_judge(*a, **kw):
        judge_calls.append((a, kw))
        return JudgeOutput(actions=[Verb(name="wait")])

    async def fake_run_narrate(*a, **kw):
        if False:
            yield None  # pragma: no cover

    from src.game.flow import narrate as narrate_mod

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    await _collect(
        run_turn(
            client=None,
            state=state_with_pending_quest,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="주변을 둘러본다",
            quest_action=("accept", "q1"),
        )
    )

    assert state_with_pending_quest.quests["q1"].status == "pending"
    assert state_with_pending_quest.pending_confirmation["kind"] == "quest_accept"
    assert judge_calls == []
