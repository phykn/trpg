import pytest

from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.flow.actions import emit_cancel_growth, emit_growth_pending
from src.flow.dirty import Dirty


@pytest.mark.asyncio
async def test_emit_growth_pending_sets_state():
    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    dirty = Dirty()
    events = []
    async for ev in emit_growth_pending(state, dirty):
        events.append(ev)
    assert state.pending_growth is not None
    assert state.pending_growth.stage == "asking_stat"
    assert events == []  # narrate produces the prose; engine emits nothing


@pytest.mark.asyncio
async def test_emit_cancel_growth_clears_state():
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    dirty = Dirty()
    events = []
    async for ev in emit_cancel_growth(state, dirty):
        events.append(ev)
    assert state.pending_growth is None
    assert events == []


@pytest.mark.asyncio
async def test_emit_cancel_growth_idempotent_when_no_pending():
    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    dirty = Dirty()
    events = []
    async for ev in emit_cancel_growth(state, dirty):
        events.append(ev)
    assert state.pending_growth is None
    assert events == []
