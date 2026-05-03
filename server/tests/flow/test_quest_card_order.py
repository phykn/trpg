"""Quest success/fail cards from `npc_dialogue_quest_check` must emit AFTER the
gm body — same ordering invariant as affinity cards (Task 18). Without this
the player sees '퀘스트 성공: ...' before reading the prose that justifies it."""

import pytest

from src.domain.entities import Character, Quest, QuestRewards, Stats
from src.flow.dirty import Dirty
from src.flow.narrate import consume_narrate
from src.llm_calls.narrate import NarrativeDelta, NarrativeFinal
from src.llm_calls.narrate.schema import NarrateOutput


def _seed_player(state):
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )


def _seed_npc(state, npc_id: str, name: str):
    state.characters[npc_id] = Character(
        id=npc_id,
        name=name,
        race_id="human",
        is_player=False,
        stats=Stats(),
    )


def _seed_quest(state, qid: str, title: str, *, giver_id: str, status: str = "active"):
    state.quests[qid] = Quest(
        id=qid,
        title=title,
        giver_id=giver_id,
        difficulty="보통",
        status=status,
        objective_text="목표",
        rewards=QuestRewards(exp=50, gold=20),
    )


@pytest.mark.asyncio
async def test_quest_success_card_emits_after_gm_body_log_entry(
    fresh_state, monkeypatch
):
    """When npc dialogue triggers a 'satisfied' judge, the success card SSE event
    and its position in state.log_entries must both come AFTER the gm body."""
    state = fresh_state
    _seed_player(state)
    _seed_npc(state, "npc_01", "촌장")
    _seed_quest(state, "q_01", "약초 회수", giver_id="npc_01")

    monkeypatch.setattr(
        "src.flow.narrate.judge_quest_progress",
        lambda *a, **kw: {
            "outcome": "satisfied",
            "reason": "보고 확인",
            "progress_delta": None,
        },
        raising=False,
    )

    final = NarrativeFinal(
        body="촌장이 고개를 끄덕입니다. 보상으로 금화를 건넵니다.",
        output=NarrateOutput(turn_summary="촌장에게 보고"),
    )

    async def stream():
        yield NarrativeDelta(text="촌장이 고개를 끄덕입니다. ")
        yield NarrativeDelta(text="보상으로 금화를 건넵니다.")
        yield final

    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            stream(),
            target_for_log="npc_01",
            dialogue_input="약초를 가져왔습니다",
            npc_dialogue_target="npc_01",
        )
    ]

    log_events = [
        (i, e) for i, e in enumerate(events) if e.get("type") == "log_entry"
    ]
    gm_idx = next(
        i for i, e in log_events if (e.get("data") or {}).get("kind") == "gm"
    )
    quest_idx = next(
        i
        for i, e in log_events
        if "퀘스트 성공" in ((e.get("data") or {}).get("text") or "")
    )
    assert quest_idx > gm_idx, (
        "quest success card SSE must emit AFTER gm body log_entry SSE",
        [(i, e) for i, e in log_events],
    )

    log_kinds_text = [(e.kind, getattr(e, "text", "")) for e in state.log_entries]
    gm_pos = next(i for i, (k, _) in enumerate(log_kinds_text) if k == "gm")
    quest_pos = next(
        i
        for i, (k, t) in enumerate(log_kinds_text)
        if k == "act" and "퀘스트 성공" in t
    )
    assert quest_pos > gm_pos, (
        "quest success card must sit AFTER gm body in state.log_entries",
        log_kinds_text,
    )
    assert state.quests["q_01"].status == "completed"


@pytest.mark.asyncio
async def test_quest_partial_progress_emits_no_card(fresh_state, monkeypatch):
    """Partial progress only mutates state — no act card should land before or after gm."""
    state = fresh_state
    _seed_player(state)
    _seed_npc(state, "npc_01", "촌장")
    _seed_quest(state, "q_01", "약초 회수", giver_id="npc_01")

    monkeypatch.setattr(
        "src.flow.narrate.judge_quest_progress",
        lambda *a, **kw: {
            "outcome": "partial",
            "reason": "1/2",
            "progress_delta": 1,
        },
        raising=False,
    )

    final = NarrativeFinal(
        body="촌장이 고개를 갸웃합니다.",
        output=NarrateOutput(turn_summary="촌장에게 진행 상황"),
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
            target_for_log="npc_01",
            dialogue_input="약초를 일부 가져왔습니다",
            npc_dialogue_target="npc_01",
        )
    ]
    quest_cards = [
        e
        for e in events
        if e.get("type") == "log_entry"
        and "퀘스트" in ((e.get("data") or {}).get("text") or "")
    ]
    assert not quest_cards, quest_cards
    assert state.quests["q_01"].status == "active"
    assert state.quests["q_01"].progress == 1
