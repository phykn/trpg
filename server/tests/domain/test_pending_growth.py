from src.domain.memory import PendingGrowth
from src.domain.state import GameState


def test_pending_growth_default_is_none():
    state = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    assert state.pending_growth is None


def test_pending_growth_can_be_set():
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    assert state.pending_growth is not None
    assert state.pending_growth.stage == "asking_stat"


def test_pending_growth_round_trip_json():
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
        pending_growth=PendingGrowth(stage="asking_stat"),
    )
    payload = state.model_dump_json()
    rebuilt = GameState.model_validate_json(payload)
    assert rebuilt.pending_growth is not None
    assert rebuilt.pending_growth.stage == "asking_stat"
