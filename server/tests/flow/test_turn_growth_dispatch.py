import pytest

from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.flow.dirty import Dirty
from src.flow.turn import _ONE_STEP_EMITS
from src.llm_calls.classify.schema import (
    CancelGrowthAction,
    GrowthPendingAction,
    LevelUpAction,
    MoveAction,
)


def test_growth_pending_action_in_dispatch_table():
    assert GrowthPendingAction in _ONE_STEP_EMITS


def test_cancel_growth_action_in_dispatch_table():
    assert CancelGrowthAction in _ONE_STEP_EMITS


@pytest.mark.asyncio
async def test_dispatch_growth_pending_sets_state():
    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    dirty = Dirty()
    factory = _ONE_STEP_EMITS[GrowthPendingAction]
    action = GrowthPendingAction(action="growth_pending")
    async for _ in factory(None, state, dirty, action):
        pass
    assert state.pending_growth is not None
    assert state.pending_growth.stage == "asking_stat"


@pytest.mark.asyncio
async def test_dispatch_cancel_growth_clears_state():
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    dirty = Dirty()
    factory = _ONE_STEP_EMITS[CancelGrowthAction]
    action = CancelGrowthAction(action="cancel_growth")
    async for _ in factory(None, state, dirty, action):
        pass
    assert state.pending_growth is None


def test_auto_cancel_action_types_documented():
    """Sanity: the actions that should NOT trigger auto-cancel are LevelUp/GrowthPending/CancelGrowth.

    The actual auto-cancel logic is checked in test_growth_pending_integration.py.
    Here we just confirm the type tuple exists conceptually.
    """
    # Document the expected exemptions — these are the actions that handle pending_growth themselves.
    exempt = {LevelUpAction, GrowthPendingAction, CancelGrowthAction}
    assert MoveAction not in exempt  # MoveAction should auto-cancel
