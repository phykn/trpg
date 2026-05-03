import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.domain.memory import PendingGrowth
from src.domain.state import GameState
from src.flow.actions import emit_level_up
from src.flow.dirty import Dirty


def _state_ready_to_level_up() -> GameState:
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["race_human"] = Race(id="race_human", name="인간", description="")
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(STR=10, CHA=10),
        is_player=True,
        level=0,
        xp_pool=100,
    )
    p.max_hp = p.hp = 20
    p.max_mp = p.mp = 10
    state.characters["player_01"] = p
    return state


@pytest.mark.asyncio
async def test_emit_level_up_clears_pending_growth():
    state = _state_ready_to_level_up()
    dirty = Dirty()
    assert state.pending_growth is not None  # precondition
    async for _ in emit_level_up(state, "player_01", "STR", "CHA", None, dirty):
        pass
    assert state.pending_growth is None
