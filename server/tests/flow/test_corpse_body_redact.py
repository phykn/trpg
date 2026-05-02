"""`consume_narrate` must strip dead-NPC quote blocks from the body before
persisting (log_entry / dialogue / state) — root-cause fix for "talking to
dead people" recurring across turns. Streaming has already emitted the
unredacted body; the `state` event at finalize clears the streaming buffer
and the persisted GM log line carries the cleaned text, so the user-visible
record and the next turn's history layer are both safe.
"""

from collections.abc import AsyncIterator

from src.llm_calls.narrate import NarrativeDelta, NarrativeFinal
from src.llm_calls.narrate.schema import NarrateOutput
from src.domain.entities import Character, Location, Stats
from src.domain.memory import TurnLogEntry
from src.flow.dirty import Dirty
from src.flow.narrate import _dead_names_in_scope, consume_narrate


async def _stream(*items) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    for it in items:
        yield it


def _seed(state, *, dead_at_player=False, dead_off_screen=False):
    """Wire a player at plaza_01 and optionally seed a dead NPC at the same
    location and/or one referenced off-screen via turn_log."""
    state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    state.locations["gate_01"] = Location(id="gate_01", name="성문")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    if dead_at_player:
        state.characters["hag"] = Character(
            id="hag",
            name="노파",
            race_id="human",
            stats=Stats(),
            location_id="plaza_01",
            alive=False,
        )
    if dead_off_screen:
        state.characters["chief"] = Character(
            id="chief",
            name="촌장",
            race_id="human",
            stats=Stats(),
            location_id="gate_01",
            alive=False,
        )
        state.turn_log.append(TurnLogEntry(turn=1, target="chief", summary="촌장 사망"))


async def _run(state, body, *, target_for_log, dialogue_input, output=None):
    output = output or NarrateOutput()
    final = NarrativeFinal(body=body, output=output)
    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            _stream(NarrativeDelta(text=body), final),
            target_for_log=target_for_log,
            dialogue_input=dialogue_input,
        )
    ]
    return events, dirty


def _last_gm_text(state):
    gm = [e for e in state.log_entries if e.kind == "gm"]
    assert gm, "no GM log entry pushed"
    return gm[-1].text


async def test_consume_narrate_redacts_same_location_dead_quote(fresh_state):
    _seed(fresh_state, dead_at_player=True)
    body = "노파가 고개를 듭니다. 「오랜만이오, 젊은이.」 손가락이 떨립니다."

    _events, dirty = await _run(
        fresh_state,
        body,
        target_for_log="hag",
        dialogue_input="노파에게 인사한다",
    )

    persisted = _last_gm_text(fresh_state)
    assert "「" not in persisted
    assert "오랜만이오" not in persisted
    assert "노파가 고개를 듭니다." in persisted  # surrounding prose kept

    # Persisted dialogue must carry the redacted body — otherwise the next
    # turn's history layer reads the raw quote and the LLM mimics it again.
    assert len(dirty.dialogue) == 1
    assert "「" not in dirty.dialogue[0].narrator


async def test_consume_narrate_redacts_off_screen_dead_quote(fresh_state):
    """Off-screen corpses (referenced via turn_log.target) must trigger
    redaction too — the player walked away but the model can still address
    the dead NPC by name from the dialogue history."""
    _seed(fresh_state, dead_off_screen=True)
    body = "촌장이 한숨을 쉽니다. 「자네는 왜 돌아왔는가.」"

    await _run(
        fresh_state,
        body,
        target_for_log=None,
        dialogue_input="촌장 생각이 난다",
    )

    persisted = _last_gm_text(fresh_state)
    assert "자네는 왜" not in persisted
    assert "「" not in persisted


async def test_consume_narrate_keeps_live_npc_quote(fresh_state):
    """Live NPC dialogue must pass through untouched even when other dead
    NPCs are in the scene — redaction is scoped to dead names only."""
    _seed(fresh_state, dead_at_player=True)
    fresh_state.characters["merchant"] = Character(
        id="merchant",
        name="상인",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    body = "상인이 미소 짓습니다. 「오늘 좋은 물건이 있소.」"

    await _run(
        fresh_state,
        body,
        target_for_log="merchant",
        dialogue_input="상인을 본다",
    )

    persisted = _last_gm_text(fresh_state)
    assert "「오늘 좋은 물건이 있소.」" in persisted


async def test_consume_narrate_no_corpses_passes_through(fresh_state):
    """No dead NPCs in scope → no redaction, body unchanged."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    body = "당신이 광장을 둘러봅니다. 분수에서 물이 떨어집니다."

    await _run(
        fresh_state,
        body,
        target_for_log=None,
        dialogue_input=None,
    )

    persisted = _last_gm_text(fresh_state)
    assert persisted == body


async def test_consume_narrate_corpse_inspection_prose_unchanged(fresh_state):
    """Looting / inspecting a body produces in-world prose without direct
    quotes — redaction must NOT touch this. The whole point of post-hoc
    redaction over upfront bypass is to preserve corpse interaction prose
    while still killing resurrected speech."""
    _seed(fresh_state, dead_at_player=True)
    body = (
        "당신이 노파의 시신 옆에 무릎을 꿇습니다. "
        "주머니를 살피지만 마땅한 것은 보이지 않습니다. "
        "차가워진 손이 가지런히 놓여 있습니다."
    )

    await _run(
        fresh_state,
        body,
        target_for_log="hag",
        dialogue_input="노파의 주머니를 뒤진다",
    )

    persisted = _last_gm_text(fresh_state)
    assert persisted == body  # bytes-identical, no redaction triggered


def test_dead_names_in_scope_same_location(fresh_state):
    _seed(fresh_state, dead_at_player=True)
    assert _dead_names_in_scope(fresh_state) == ["노파"]


def test_dead_names_in_scope_off_screen_via_turn_log(fresh_state):
    _seed(fresh_state, dead_off_screen=True)
    assert _dead_names_in_scope(fresh_state) == ["촌장"]


def test_dead_names_in_scope_excludes_alive(fresh_state):
    _seed(fresh_state)  # no dead seeded
    fresh_state.characters["alive"] = Character(
        id="alive",
        name="살아있음",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    assert _dead_names_in_scope(fresh_state) == []
