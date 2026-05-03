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
