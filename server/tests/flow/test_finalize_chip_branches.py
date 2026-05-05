"""finalize emits the SSE `suggestions` event from `dirty.narrate_suggestions`.

When narrate ran (consume_narrate populated narrate_suggestions), finalize
ferries those chips out. Receipt-only / game-over / re-visit-move turns leave
narrate_suggestions=None, so finalize emits an empty list — the client strip
clears instead of carrying stale picks across turns.

Engine-only test paths (`to_front_fn=None`) stay quiet — same gate as the
`state` event.
"""

import pytest

from src.domain.entities import Character, Location, Stats
from src.domain.state import GameState
from src.flow.dirty import Dirty, finalize
from src.wire.to_front import to_front_state


class _FakeRepo:
    async def save_entity(self, *a, **kw):
        pass

    async def append_log_entries(self, *a, **kw):
        pass

    async def append_history_entries(self, *a, **kw):
        pass

    async def append_dialogue_entries(self, *a, **kw):
        pass

    async def save_meta(self, *a, **kw):
        pass


def _state() -> GameState:
    s = GameState(game_id="t", profile="default", player_id="player_01")
    s.locations["loc_a"] = Location(id="loc_a", name="현장")
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_a",
    )
    return s


@pytest.mark.asyncio
async def test_finalize_emits_narrate_suggestions_when_set():
    state = _state()
    dirty = Dirty()
    dirty.narrate_suggestions = ["수락한다", "거절한다"]
    events = [ev async for ev in finalize(state, _FakeRepo(), dirty, to_front_state)]
    sug = next(ev for ev in events if ev["type"] == "suggestions")
    assert sug["data"]["items"] == ["수락한다", "거절한다"]


@pytest.mark.asyncio
async def test_finalize_emits_empty_suggestions_when_none():
    """receipt-only turn: narrate didn't run → narrate_suggestions stays None."""
    state = _state()
    dirty = Dirty()
    assert dirty.narrate_suggestions is None
    events = [ev async for ev in finalize(state, _FakeRepo(), dirty, to_front_state)]
    sug = next(ev for ev in events if ev["type"] == "suggestions")
    assert sug["data"]["items"] == []


@pytest.mark.asyncio
async def test_finalize_emits_empty_suggestions_when_narrate_ran_with_no_chips():
    """narrate ran but emitted []; still pass through that empty list (not None)."""
    state = _state()
    dirty = Dirty()
    dirty.narrate_suggestions = []
    events = [ev async for ev in finalize(state, _FakeRepo(), dirty, to_front_state)]
    sug = next(ev for ev in events if ev["type"] == "suggestions")
    assert sug["data"]["items"] == []


@pytest.mark.asyncio
async def test_finalize_skips_suggestions_event_without_to_front_fn():
    state = _state()
    dirty = Dirty()
    dirty.narrate_suggestions = ["a", "b"]
    events = [ev async for ev in finalize(state, _FakeRepo(), dirty, to_front_fn=None)]
    types = [ev["type"] for ev in events]
    assert "suggestions" not in types
