"""Affinity system cards: apply_changes captures deltas, consume_narrate emits cards.

EXP cards are deferred — `xp_pool` is engine-owned (CHAR_FORBIDDEN) and engine xp paths
(award_kill_xp / grant_roll_xp / quest reward) bypass apply_changes. `exp_deltas` key
on the apply_changes result is reserved for a future side-channel; today it is always [].
"""

import pytest

from src.domain.entities import Character, Stats
from src.engines.apply import apply_changes
from src.flow.dirty import Dirty
from src.flow.narrate import consume_narrate
from src.llm_calls.narrate import NarrativeFinal
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


def test_exp_deltas_key_present_but_empty(fresh_state):
    """`exp_deltas` is reserved on the apply_changes return dict (always [] today)."""
    _seed_player(fresh_state)
    result = apply_changes(fresh_state, [], set())
    assert result["exp_deltas"] == []


def test_affinity_friendly_success_captured(fresh_state):
    _seed_player(fresh_state)
    _seed_npc(fresh_state, "npc_01", "도린")
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "npc_01",
                "grade": "success",
                "intent": "friendly",
            }
        ],
        set(),
    )
    # +5 per RULES.social.affinity_success.
    assert result["affinity_deltas"] == [("npc_01", 5)]


def test_affinity_hostile_intent_captured_with_sign(fresh_state):
    _seed_player(fresh_state)
    _seed_npc(fresh_state, "npc_01", "도린")
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "npc_01",
                "grade": "success",
                "intent": "hostile",
            }
        ],
        set(),
    )
    # Hostile success → engine flips sign; affinity_deltas reflects the final signed delta.
    deltas = result["affinity_deltas"]
    assert len(deltas) == 1
    npc_id, delta = deltas[0]
    assert npc_id == "npc_01"
    assert delta < 0


def test_affinity_clamp_no_movement_no_delta(fresh_state):
    _seed_player(fresh_state)
    _seed_npc(fresh_state, "npc_01", "도린")
    fresh_state.characters["npc_01"].relations["player_01"] = 100
    result = apply_changes(
        fresh_state,
        [
            {
                "type": "affinity",
                "actor": "player_01",
                "target": "npc_01",
                "grade": "success",
                "intent": "friendly",
            }
        ],
        set(),
    )
    # Already at +100 cap → no movement → no delta entry.
    assert result["affinity_deltas"] == []


@pytest.mark.asyncio
async def test_consume_narrate_emits_affinity_card(fresh_state):
    state = fresh_state
    _seed_player(state)
    _seed_npc(state, "npc_01", "도린")

    final = NarrativeFinal(
        body="도린이 흐뭇하게 미소 짓습니다.",
        output=NarrateOutput(
            turn_summary="도린 칭찬",
            state_changes=[
                {
                    "type": "affinity",
                    "actor": "player_01",
                    "target": "npc_01",
                    "grade": "success",
                    "intent": "friendly",
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
    assert any("도린 호감도 +5" in (e["data"]["text"] or "") for e in act_events), (
        events
    )
    assert any("도린 호감도 +5" in e.summary for e in state.turn_log), state.turn_log


@pytest.mark.asyncio
async def test_affinity_card_emits_after_gm_body_log_entry(fresh_state):
    """Affinity card is a reaction to the body — its SSE event and its position in
    state.log_entries must both come AFTER the gm body so the player reads the prose
    before the receipt that justifies it."""
    from src.llm_calls.narrate import NarrativeDelta

    state = fresh_state
    _seed_player(state)
    _seed_npc(state, "npc_01", "에드릭")

    final = NarrativeFinal(
        body="당신은 고개를 살짝 숙입니다. 에드릭이 미소 짓습니다.",
        output=NarrateOutput(
            turn_summary="에드릭에게 인사",
            state_changes=[
                {
                    "type": "affinity",
                    "actor": "player_01",
                    "target": "npc_01",
                    "grade": "success",
                    "intent": "friendly",
                }
            ],
        ),
    )

    async def stream():
        yield NarrativeDelta(text="당신은 고개를 살짝 숙입니다. ")
        yield NarrativeDelta(text="에드릭이 미소 짓습니다.")
        yield final

    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            stream(),
            target_for_log=None,
            dialogue_input="에드릭에게 인사한다",
        )
    ]
    log_events = [
        (i, e)
        for i, e in enumerate(events)
        if e.get("type") == "log_entry"
    ]
    gm_idx = next(
        i for i, e in log_events if (e.get("data") or {}).get("kind") == "gm"
    )
    aff_idx = next(
        i
        for i, e in log_events
        if "호감도" in ((e.get("data") or {}).get("text") or "")
    )
    assert aff_idx > gm_idx, (
        "affinity card SSE must emit AFTER gm body log_entry SSE",
        [(i, e) for i, e in log_events],
    )

    log_kinds_text = [(e.kind, getattr(e, "text", "")) for e in state.log_entries]
    gm_pos = next(i for i, (k, _) in enumerate(log_kinds_text) if k == "gm")
    aff_pos = next(
        i for i, (k, t) in enumerate(log_kinds_text) if k == "act" and "호감도" in t
    )
    assert aff_pos > gm_pos, (
        "affinity card must sit AFTER gm body in state.log_entries",
        log_kinds_text,
    )
