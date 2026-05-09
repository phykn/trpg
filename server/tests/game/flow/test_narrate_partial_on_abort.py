"""Client-abort during narrate streaming preserves the streamed prose as a
GMLogEntry instead of throwing it away — matches 'cut off mid-sentence'
semantics. Extract artifacts (state_changes, memory) are skipped because the
JSON tail never arrived."""

import asyncio

import pytest

from src.game.domain.entities import Character, Location, Race, Stats
from src.game.domain.memory import GMLogEntry
from src.game.domain.state import GameState
from src.game.flow.dirty import Dirty
from src.game.flow.narrate import consume_narrate
from src.llm.calls.narrate import NarrativeDelta


def _state() -> GameState:
    s = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    s.races["race_human"] = Race(id="race_human", name="인간", description="인간 종족")
    s.locations["loc_01"] = Location(id="loc_01", name="광장")
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        is_player=True,
    )
    p.max_hp = p.hp = 20
    p.max_mp = p.mp = 10
    s.characters["player_01"] = p
    return s


async def _stream_then_cancel(chunks: list[str]):
    for c in chunks:
        yield NarrativeDelta(text=c)
    raise asyncio.CancelledError


@pytest.mark.asyncio
async def test_partial_body_persisted_on_cancel():
    """Stop mid-stream → collected chunks land as a GMLogEntry in dirty.log."""
    state = _state()
    dirty = Dirty()
    stream = _stream_then_cancel(["당신은 ", "조용히 ", "촌장을 바라봅니다."])

    with pytest.raises(asyncio.CancelledError):
        async for _ in consume_narrate(
            state,
            dirty,
            stream,
            target_for_log=None,
            dialogue_input="촌장에게 인사한다",
        ):
            pass

    gm_entries = [e for e in dirty.log if isinstance(e, GMLogEntry)]
    assert len(gm_entries) == 1
    assert gm_entries[0].text == "당신은 조용히 촌장을 바라봅니다."
    assert any(d.player == "촌장에게 인사한다" for d in dirty.dialogue)


@pytest.mark.asyncio
async def test_cancel_before_any_chunk_pushes_nothing():
    """Cancel before the first delta → no GMLogEntry (nothing to preserve)."""
    state = _state()
    dirty = Dirty()
    stream = _stream_then_cancel([])

    with pytest.raises(asyncio.CancelledError):
        async for _ in consume_narrate(
            state,
            dirty,
            stream,
            target_for_log=None,
            dialogue_input="x",
        ):
            pass

    assert not [e for e in dirty.log if isinstance(e, GMLogEntry)]
    assert not dirty.dialogue


@pytest.mark.asyncio
async def test_cancel_skips_dialogue_when_dialogue_input_none():
    """Intro / button-only paths pass dialogue_input=None — partial body still
    lands as a GMLogEntry but no dialogue row is pushed."""
    state = _state()
    dirty = Dirty()
    stream = _stream_then_cancel(["인트로 본문 일부."])

    with pytest.raises(asyncio.CancelledError):
        async for _ in consume_narrate(
            state,
            dirty,
            stream,
            target_for_log=None,
            dialogue_input=None,
        ):
            pass

    gm_entries = [e for e in dirty.log if isinstance(e, GMLogEntry)]
    assert len(gm_entries) == 1
    assert gm_entries[0].text == "인트로 본문 일부."
    assert not dirty.dialogue
