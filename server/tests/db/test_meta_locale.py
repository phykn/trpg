from src.game.domain.state import GameState


def test_gamestate_default_locale_is_ko():
    s = GameState(game_id="g_test", profile="p", player_id="p1")
    assert s.locale == "ko"


def test_gamestate_locale_overridable():
    s = GameState(game_id="g_test", profile="p", player_id="p1", locale="en")
    assert s.locale == "en"
