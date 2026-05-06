from src.game.domain.state import GameState
from src.db.store import _Meta, _meta_from_state


def test_gamestate_default_locale_is_ko():
    s = GameState(game_id="g_test", profile="p", player_id="p1")
    assert s.locale == "ko"


def test_gamestate_locale_overridable():
    s = GameState(game_id="g_test", profile="p", player_id="p1", locale="en")
    assert s.locale == "en"


def test_meta_roundtrip_preserves_locale():
    s = GameState(game_id="g1", profile="p", player_id="p1", locale="en")
    meta = _meta_from_state(s)
    assert meta.locale == "en"
    payload = meta.model_dump_json()
    restored = _Meta.model_validate_json(payload)
    assert restored.locale == "en"


def test_meta_legacy_payload_defaults_to_ko():
    legacy = '{"game_id":"g","profile":"p","player_id":"p1"}'
    meta = _Meta.model_validate_json(legacy)
    assert meta.locale == "ko"
