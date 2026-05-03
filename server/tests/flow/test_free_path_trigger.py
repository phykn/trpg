"""Free-path judge triggered on turn end + NPC dialogue."""

import tempfile
import pytest
from src.domain.entities import Character, Location, Quest, Stats
from src.domain.state import GameState
from src.engines.quest import apply_judge_result
from src.flow.turn import end_turn_quest_check
from src.flow.narrate import npc_dialogue_quest_check
from src.flow import narrate as narrate_mod
from src.llm_calls.classify.schema import PassAction
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


# ---------------------------------------------------------------------------
# Helpers


def _make_state(*, quest_status="active", giver_id="npc_01"):
    state = GameState(game_id="t", profile="default", player_id="player_01")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )
    state.characters[giver_id] = Character(
        id=giver_id,
        name="NPC",
        race_id="human",
        stats=Stats(),
    )
    state.quests["q1"] = Quest(
        id="q1",
        title="테스트 퀘스트",
        giver_id=giver_id,
        difficulty="보통",
        status=quest_status,
        objective_text="약탈자 처치",
    )
    return state


# ---------------------------------------------------------------------------
# apply_judge_result


def test_apply_judge_result_satisfied():
    state = _make_state()
    changed = apply_judge_result(
        state, "q1", {"outcome": "satisfied", "reason": "ok", "progress_delta": None}
    )
    assert changed is True
    assert state.quests["q1"].status == "completed"


def test_apply_judge_result_partial():
    state = _make_state()
    changed = apply_judge_result(
        state, "q1", {"outcome": "partial", "reason": "1/2", "progress_delta": 1}
    )
    assert changed is True
    assert state.quests["q1"].status == "active"
    assert state.quests["q1"].progress == 1


def test_apply_judge_result_partial_accumulates():
    state = _make_state()
    apply_judge_result(
        state, "q1", {"outcome": "partial", "reason": "1/2", "progress_delta": 1}
    )
    apply_judge_result(
        state, "q1", {"outcome": "partial", "reason": "2/2", "progress_delta": 1}
    )
    assert state.quests["q1"].progress == 2


def test_apply_judge_result_rejected_no_op():
    state = _make_state()
    changed = apply_judge_result(
        state, "q1", {"outcome": "rejected", "reason": "no", "progress_delta": None}
    )
    assert changed is False
    assert state.quests["q1"].status == "active"


def test_apply_judge_result_skip_non_active():
    state = _make_state(quest_status="completed")
    changed = apply_judge_result(
        state, "q1", {"outcome": "satisfied", "reason": "...", "progress_delta": None}
    )
    assert changed is False
    assert state.quests["q1"].status == "completed"  # already completed, immune


def test_apply_judge_result_missing_quest_no_crash():
    state = _make_state()
    changed = apply_judge_result(
        state,
        "nonexistent",
        {"outcome": "satisfied", "reason": "ok", "progress_delta": None},
    )
    assert changed is False


# ---------------------------------------------------------------------------
# end_turn_quest_check


def test_active_quest_judge_satisfied_completes_quest(monkeypatch):
    from src.domain.memory import TurnLogEntry

    state = _make_state()
    state.turn_log.append(TurnLogEntry(turn=1, summary="고블린 처치"))

    judge_calls = []

    def mock_judge(quest, history, claim, npc_context):
        judge_calls.append(quest["id"])
        return {
            "outcome": "satisfied",
            "reason": "history confirms",
            "progress_delta": None,
        }

    monkeypatch.setattr("src.flow.turn.judge_quest_progress", mock_judge, raising=False)

    end_turn_quest_check(state)

    assert "q1" in judge_calls
    assert state.quests["q1"].status == "completed"


def test_no_active_quests_no_judge_call(monkeypatch):
    from src.domain.memory import TurnLogEntry

    state = _make_state(quest_status="completed")
    state.turn_log.append(TurnLogEntry(turn=1, summary="이벤트"))

    judge_calls = []

    def mock_judge(*a, **kw):
        judge_calls.append(True)
        return {"outcome": "rejected", "reason": "", "progress_delta": None}

    monkeypatch.setattr("src.flow.turn.judge_quest_progress", mock_judge, raising=False)
    end_turn_quest_check(state)
    assert judge_calls == []


def test_empty_history_skips_judge(monkeypatch):
    state = _make_state()
    # turn_log is empty — no history
    judge_calls = []

    def mock_judge(*a, **kw):
        judge_calls.append(True)
        return {"outcome": "satisfied", "reason": "", "progress_delta": None}

    monkeypatch.setattr("src.flow.turn.judge_quest_progress", mock_judge, raising=False)
    end_turn_quest_check(state)
    assert judge_calls == []


# ---------------------------------------------------------------------------
# npc_dialogue_quest_check


def test_npc_dialogue_matching_giver_triggers_judge(monkeypatch):
    state = _make_state(giver_id="npc_01")

    judge_calls = []

    def mock_judge(quest, history, claim, npc_context):
        judge_calls.append(quest["id"])
        return {
            "outcome": "satisfied",
            "reason": "claim verified",
            "progress_delta": None,
        }

    monkeypatch.setattr(
        "src.flow.narrate.judge_quest_progress", mock_judge, raising=False
    )

    npc_dialogue_quest_check(state, claim="처치했습니다", npc_id="npc_01")

    assert "q1" in judge_calls
    assert state.quests["q1"].status == "completed"


def test_npc_dialogue_wrong_npc_skips_judge(monkeypatch):
    state = _make_state(giver_id="npc_01")

    judge_calls = []

    def mock_judge(*a, **kw):
        judge_calls.append(True)
        return {"outcome": "satisfied", "reason": "", "progress_delta": None}

    monkeypatch.setattr(
        "src.flow.narrate.judge_quest_progress", mock_judge, raising=False
    )

    npc_dialogue_quest_check(state, claim="처치했습니다", npc_id="npc_other")

    assert judge_calls == []
    assert state.quests["q1"].status == "active"


def test_npc_dialogue_completed_quest_skipped(monkeypatch):
    state = _make_state(quest_status="completed", giver_id="npc_01")

    judge_calls = []

    def mock_judge(*a, **kw):
        judge_calls.append(True)
        return {"outcome": "satisfied", "reason": "", "progress_delta": None}

    monkeypatch.setattr(
        "src.flow.narrate.judge_quest_progress", mock_judge, raising=False
    )

    npc_dialogue_quest_check(state, claim="처치했습니다", npc_id="npc_01")

    assert judge_calls == []


# ---------------------------------------------------------------------------
# apply_judge_result — success_reason propagation


def test_apply_judge_result_satisfied_uses_result_reason():
    state = _make_state()
    apply_judge_result(
        state,
        "q1",
        {"outcome": "satisfied", "reason": "claim verified", "progress_delta": None},
    )
    assert state.quests["q1"].success_reason == "claim verified"


def test_apply_judge_result_satisfied_fallback_when_reason_missing():
    state = _make_state()
    apply_judge_result(state, "q1", {"outcome": "satisfied"})
    assert state.quests["q1"].success_reason == "free_path_satisfied"


def test_apply_judge_result_satisfied_fallback_when_reason_empty():
    state = _make_state()
    apply_judge_result(state, "q1", {"outcome": "satisfied", "reason": ""})
    assert state.quests["q1"].success_reason == "free_path_satisfied"


# ---------------------------------------------------------------------------
# stream_narrate_tail — npc_dialogue_quest_check wiring


async def test_stream_narrate_tail_calls_npc_dialogue_check_for_npc_target(
    fresh_state, monkeypatch
):
    """PassAction targeting an NPC character must invoke npc_dialogue_quest_check."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
        fresh_state.characters["player_01"] = Character(
            id="player_01",
            name="주",
            race_id="human",
            is_player=True,
            location_id="plaza_01",
            stats=Stats(),
        )
        fresh_state.characters["npc_01"] = Character(
            id="npc_01",
            name="NPC",
            race_id="human",
            location_id="plaza_01",
            stats=Stats(),
        )

        captured: list[dict] = []

        def fake_npc_check(state, *, claim, npc_id, dirty=None):
            captured.append({"claim": claim, "npc_id": npc_id})

        monkeypatch.setattr(narrate_mod, "npc_dialogue_quest_check", fake_npc_check)

        async def fake_run_narrate(*a, **kw):
            if False:
                yield None  # pragma: no cover

        monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

        from src.flow.dirty import Dirty
        from src.flow.narrate import stream_narrate_tail

        action = PassAction(action="pass", targets=["npc_01"])
        dirty = Dirty()
        events = [
            ev
            async for ev in stream_narrate_tail(
                client=None,
                state=fresh_state,
                scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
                player_input="퀘스트를 완료했습니다",
                dirty=dirty,
                to_front_fn=None,
                action=action,
                graph=fresh_state.graph(),
            )
        ]

        assert len(captured) == 1
        assert captured[0]["npc_id"] == "npc_01"
        assert captured[0]["claim"] == "퀘스트를 완료했습니다"


async def test_stream_narrate_tail_skips_npc_check_for_player_target(
    fresh_state, monkeypatch
):
    """PassAction targeting the player itself must NOT invoke npc_dialogue_quest_check."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fresh_state.characters["player_01"] = Character(
            id="player_01",
            name="주",
            race_id="human",
            is_player=True,
            stats=Stats(),
        )

        captured: list[dict] = []

        def fake_npc_check(state, *, claim, npc_id, dirty=None):
            captured.append({"npc_id": npc_id})

        monkeypatch.setattr(narrate_mod, "npc_dialogue_quest_check", fake_npc_check)

        async def fake_run_narrate(*a, **kw):
            if False:
                yield None  # pragma: no cover

        monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

        from src.flow.dirty import Dirty
        from src.flow.narrate import stream_narrate_tail

        action = PassAction(action="pass", targets=["player_01"])
        dirty = Dirty()
        [
            ev
            async for ev in stream_narrate_tail(
                client=None,
                state=fresh_state,
                scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
                player_input="자신을 살펴본다",
                dirty=dirty,
                to_front_fn=None,
                action=action,
                graph=fresh_state.graph(),
            )
        ]

        assert captured == []


async def test_stream_narrate_tail_skips_npc_check_when_no_target(
    fresh_state, monkeypatch
):
    """PassAction with no targets must NOT invoke npc_dialogue_quest_check."""
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )

    captured: list[dict] = []

    def fake_npc_check(state, *, claim, npc_id, dirty=None):
        captured.append({"npc_id": npc_id})

    monkeypatch.setattr(narrate_mod, "npc_dialogue_quest_check", fake_npc_check)

    async def fake_run_narrate(*a, **kw):
        if False:
            yield None  # pragma: no cover

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    with tempfile.TemporaryDirectory() as tmp_dir:
        from src.flow.dirty import Dirty
        from src.flow.narrate import stream_narrate_tail

        action = PassAction(action="pass")
        dirty = Dirty()
        [
            ev
            async for ev in stream_narrate_tail(
                client=None,
                state=fresh_state,
                scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
                player_input="주변을 살핀다",
                dirty=dirty,
                to_front_fn=None,
                action=action,
                graph=fresh_state.graph(),
            )
        ]

        assert captured == []
