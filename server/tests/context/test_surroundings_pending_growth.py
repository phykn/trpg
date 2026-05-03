from src.context.surroundings import build_surroundings
from src.domain.entities import Character, Location, Race, Stats
from src.domain.memory import PendingGrowth
from src.domain.state import GameState


def _state_with_player(pending: PendingGrowth | None = None) -> GameState:
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=pending,
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["race_human"] = Race(id="race_human", name="인간", description="")
    state.characters["player_01"] = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        is_player=True,
    )
    return state


def test_surroundings_includes_pending_growth_when_set():
    state = _state_with_player(PendingGrowth(stage="asking_stat"))
    surroundings = build_surroundings(state, "player_01")
    assert surroundings.get("pending_growth") == {"stage": "asking_stat"}


def test_surroundings_pending_growth_is_none_by_default():
    state = _state_with_player(None)
    surroundings = build_surroundings(state, "player_01")
    assert surroundings.get("pending_growth") is None
