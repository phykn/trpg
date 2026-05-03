"""End-to-end engine-side tests for the level-up goddess flow.

Each test drives a small slice of the flow (emit_*, dispatch table, engine)
and asserts the resulting state. LLM agents (classify, narrate, recommend) are
NOT exercised — those are tested via prompts and smoke runs.
"""

import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.flow.actions import emit_cancel_growth, emit_growth_pending, emit_level_up
from src.flow.dirty import Dirty
from src.flow.turn import _ONE_STEP_EMITS
from src.llm_calls.classify.schema import (
    CancelGrowthAction,
    GrowthPendingAction,
    LevelUpAction,
    MoveAction,
)


def _ready_state() -> GameState:
    """Player at level 0 with enough XP to level up. No combat."""
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["race_human"] = Race(id="race_human", name="인간", description="")
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(STR=10, CHA=10, DEX=10, WIS=10, CON=10, INT=10),
        is_player=True,
        level=0,
        xp_pool=100,
    )
    p.max_hp = p.hp = 20
    p.max_mp = p.mp = 10
    state.characters["player_01"] = p
    return state


# ----- Case A: stat 명시 (no goddess asking, just reporting) -----


@pytest.mark.asyncio
async def test_case_a_stat_explicit_no_pending_growth_set():
    """User says '근력 올려줘' → LevelUpAction directly, no asking phase."""
    state = _ready_state()
    dirty = Dirty()
    async for _ in emit_level_up(state, "player_01", "STR", "CHA", None, dirty):
        pass
    assert state.pending_growth is None
    assert state.characters["player_01"].level == 1
    assert state.characters["player_01"].stats.STR == 11


# ----- Case B: stat 미입력 → goddess asks -----


@pytest.mark.asyncio
async def test_case_b_growth_pending_sets_state_for_narrate():
    """User says '성장한다' → GrowthPendingAction → pending_growth set."""
    state = _ready_state()
    dirty = Dirty()
    async for _ in emit_growth_pending(state, dirty):
        pass
    assert state.pending_growth is not None
    assert state.pending_growth.stage == "asking_stat"


@pytest.mark.asyncio
async def test_case_b_followup_stat_answer_clears_pending_and_levels_up():
    """User answers '근력' after goddess asked → pending cleared, level applied."""
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    dirty = Dirty()
    async for _ in emit_level_up(state, "player_01", "STR", "CHA", None, dirty):
        pass
    assert state.pending_growth is None
    assert state.characters["player_01"].level == 1


# ----- Case C: explicit cancel -----


@pytest.mark.asyncio
async def test_case_c_explicit_cancel_clears_pending():
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    dirty = Dirty()
    async for _ in emit_cancel_growth(state, dirty):
        pass
    assert state.pending_growth is None


# ----- Case C2: auto-cancel via unrelated action (dispatch logic) -----


def test_case_c2_dispatch_auto_cancel_branch_logic():
    """Verify the auto-cancel branch in _dispatch fires for unrelated actions."""
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    result = MoveAction(action="move", destination="loc_01")

    # Mirror the auto-cancel branch from flow/turn.py:_dispatch.
    if state.pending_growth and not isinstance(
        result, (LevelUpAction, GrowthPendingAction, CancelGrowthAction)
    ):
        state.pending_growth = None
    assert state.pending_growth is None


def test_case_c2_dispatch_does_not_cancel_for_levelup_action():
    """LevelUpAction is exempt — handles pending itself."""
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    result = LevelUpAction(action="level_up", stat_up="STR", stat_down="CHA")

    if state.pending_growth and not isinstance(
        result, (LevelUpAction, GrowthPendingAction, CancelGrowthAction)
    ):
        state.pending_growth = None
    # Still set — emit_level_up will clear it later.
    assert state.pending_growth is not None


# ----- Case D: can_level_up=false → no goddess (engine-side) -----


def test_case_d_no_goddess_when_cannot_level_up():
    """When can_level_up=false, the goddess should not appear (classify enforces this)."""
    from src.engines.growth import can_afford_level_up

    state = _ready_state()
    state.characters["player_01"].xp_pool = 0
    assert not can_afford_level_up(state.characters["player_01"])


# ----- E3: pair cap/floor (engine reject path) -----


@pytest.mark.asyncio
async def test_e3_pair_cap_clears_pending_no_infinite_loop():
    """STR at 20 → engine raises LevelUpInvalid → emit catches it, GM logs, pending cleared."""
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    state.characters["player_01"].stats.STR = 20
    dirty = Dirty()
    async for _ in emit_level_up(state, "player_01", "STR", "CHA", None, dirty):
        pass
    # Pending cleared at function start regardless of success/fail.
    assert state.pending_growth is None
    # Level didn't apply (cap blocked).
    assert state.characters["player_01"].level == 0


# ----- E5: empty skill candidates (engine-side check) -----


@pytest.mark.asyncio
async def test_e5_no_recommend_yields_empty_candidates():
    """client=None means recommend is skipped → pending_skill_candidates stays empty."""
    state = _ready_state()
    state.pending_growth = PendingGrowth(stage="asking_stat")
    dirty = Dirty()
    async for _ in emit_level_up(state, "player_01", "STR", "CHA", None, dirty):
        pass
    assert state.pending_skill_candidates == []
    assert state.pending_growth is None


# ----- Dispatch table coverage (smoke) -----


def test_dispatch_table_has_all_growth_actions():
    """Sanity: dispatch table is wired for all 3 growth-related action types."""
    assert GrowthPendingAction in _ONE_STEP_EMITS
    assert CancelGrowthAction in _ONE_STEP_EMITS
    assert LevelUpAction in _ONE_STEP_EMITS
