"""Quest-start system card: locked → active flip surfaces an act log + turn_log."""

import pytest

from src.domain.entities import Character, Quest, Stats
from src.engines.apply import apply_changes
from src.flow.dirty import Dirty
from src.flow.narrate import consume_narrate
from src.llm_calls.narrate import NarrativeFinal
from src.llm_calls.narrate.schema import NarrateOutput


def _seed_quest(state, qid: str, title: str, status: str) -> None:
    state.quests[qid] = Quest(
        id=qid,
        title=title,
        giver_id="npc_01",
        difficulty="normal",
        status=status,
    )


def test_apply_changes_returns_dict_with_new_keys(fresh_state):
    result = apply_changes(fresh_state, [], set())
    assert "started_quests" in result
    assert "affinity_deltas" in result
    assert "exp_deltas" in result
    assert result["started_quests"] == []


def test_locked_to_active_returns_started_quest_id(fresh_state):
    _seed_quest(fresh_state, "q_01", "사라진 약초꾸러미", "locked")
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "set",
                "entity": "quests",
                "id": "q_01",
                "field": "status",
                "value": "active",
            }
        ],
        set(),
    )
    assert result["started_quests"] == ["q_01"]
    assert fresh_state.quests["q_01"].status == "active"


def test_already_active_no_started_quest(fresh_state):
    _seed_quest(fresh_state, "q_01", "이미 시작됨", "active")
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "set",
                "entity": "quests",
                "id": "q_01",
                "field": "status",
                "value": "active",
            }
        ],
        set(),
    )
    assert result["started_quests"] == []


def test_pending_to_active_counts_as_started(fresh_state):
    """Quests that pre-staged through `pending` still emit a card on activation."""
    _seed_quest(fresh_state, "q_01", "수락된 의뢰", "pending")
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "set",
                "entity": "quests",
                "id": "q_01",
                "field": "status",
                "value": "active",
            }
        ],
        set(),
    )
    assert result["started_quests"] == ["q_01"]


def test_rejected_quest_set_does_not_count(fresh_state):
    """Bad value should not slip a started quest entry."""
    _seed_quest(fresh_state, "q_01", "t", "locked")
    # Forbidden field — rejection path shouldn't even attempt status compare.
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "set",
                "entity": "quests",
                "id": "q_01",
                "field": "title",
                "value": "x",
            }
        ],
        set(),
    )
    assert result["started_quests"] == []
    assert result["applied"] == 0


@pytest.mark.asyncio
async def test_consume_narrate_emits_quest_start_card(fresh_state):
    """Integration: narrate stream that flips a quest emits the act card SSE event."""
    state = fresh_state
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )
    _seed_quest(state, "q_01", "마을의 부탁", "locked")

    final = NarrativeFinal(
        body="당신은 의뢰를 받았습니다.",
        output=NarrateOutput(
            turn_summary="의뢰 수락",
            state_changes=[
                {
                    "type": "set",
                    "entity": "quests",
                    "id": "q_01",
                    "field": "status",
                    "value": "active",
                }
            ],
        ),
    )

    async def stream():
        yield final

    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            stream(),
            target_for_log=None,
            dialogue_input=None,
        )
    ]
    act_events = [
        e
        for e in events
        if e.get("type") == "log_entry" and (e.get("data") or {}).get("kind") == "act"
    ]
    assert any(
        "퀘스트 시작: 마을의 부탁" in (e["data"]["text"] or "") for e in act_events
    ), events
    # turn_log echoed for next-turn engine context.
    assert any("퀘스트 시작: 마을의 부탁" in e.summary for e in state.turn_log), (
        state.turn_log
    )


@pytest.mark.asyncio
async def test_consume_narrate_no_card_when_status_unchanged(fresh_state):
    state = fresh_state
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )
    _seed_quest(state, "q_01", "이미 진행 중", "active")

    final = NarrativeFinal(
        body="당신은 길을 걷습니다.",
        output=NarrateOutput(
            turn_summary="이동",
            state_changes=[
                {
                    "type": "set",
                    "entity": "quests",
                    "id": "q_01",
                    "field": "status",
                    "value": "active",
                }
            ],
        ),
    )

    async def stream():
        yield final

    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            stream(),
            target_for_log=None,
            dialogue_input=None,
        )
    ]
    assert not any(
        "퀘스트 시작" in (e.get("data", {}).get("text") or "")
        for e in events
        if e.get("type") == "log_entry"
    ), events
