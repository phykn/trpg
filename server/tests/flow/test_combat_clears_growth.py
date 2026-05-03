import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.engines import combat as combat_engine


def _state_with_pending_and_enemy() -> GameState:
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["race_human"] = Race(
        id="race_human", name="인간", description="인간 종족"
    )
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
    state.characters["player_01"] = p
    e = Character(
        id="enemy_01",
        name="고블린",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
    )
    e.max_hp = e.hp = 10
    e.max_mp = e.mp = 0
    state.characters["enemy_01"] = e
    return state


def test_engine_start_combat_does_not_clear_pending_growth():
    """Sanity: clearing happens at the FLOW layer (combat_phase), not in the engine.

    If this test fails, somebody added pending_growth handling to engine combat
    code — re-evaluate whether the clear belongs in flow or engine.
    """
    state = _state_with_pending_and_enemy()
    combat_engine.start_combat(state, ["enemy_01"])
    # Engine doesn't manage flow-level pending state.
    assert state.pending_growth is not None


@pytest.mark.asyncio
async def test_combat_phase_entry_clears_pending_growth():
    """E4: combat phase entry must clear pending_growth so the goddess scene
    doesn't carry into combat narrate."""
    from unittest.mock import AsyncMock
    from src.flow.combat_phase import start_combat_and_drive_auto
    from src.flow.dirty import Dirty

    # PlayerAction lives in flow.combat_phase — find it via that module's namespace.
    from src.flow import combat_phase as cp

    PlayerAction = cp.PlayerAction

    state = _state_with_pending_and_enemy()
    dirty = Dirty()
    graph = state.graph()
    gen = start_combat_and_drive_auto(
        None,  # client
        state,
        AsyncMock(),  # scenario_repo
        ["enemy_01"],
        dirty,
        None,  # rng
        player_input="공격",
        player_action=PlayerAction(kind="attack", skill_id=None, targets=["enemy_01"]),
        graph=graph,
    )
    # Drain at least one event — the entry-side effect (clear) happens before any yield.
    try:
        await gen.__anext__()
    except (StopAsyncIteration, Exception):
        pass
    assert state.pending_growth is None
