import json
from pathlib import Path

import pytest

from src.game.flow.init import PlayerInput, init_game
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.db._schema import _Meta, _meta_from_state
from src.game.domain.state import GameState


def _write_minimal_seed(profile_dir: Path) -> None:
    pdir = profile_dir / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(
        json.dumps({"start_location_id": "plaza_01"}),
        encoding="utf-8",
    )
    (pdir / "player_template.json").write_text(
        json.dumps({"id": "player_01"}), encoding="utf-8"
    )
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(
        json.dumps(
            {"id": "human", "name": "인간", "description": "x", "racial_skills": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "locations").mkdir()
    (pdir / "locations" / "plaza.json").write_text(
        json.dumps({"id": "plaza_01", "name": "광장"}, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_init_game_persists_locale_en(tmp_path):
    """init_game(locale='en') stores it; round-trip via load_game confirms persistence."""
    profile_dir = tmp_path / "profiles"
    saves_dir = str(tmp_path / "saves")
    _write_minimal_seed(profile_dir)
    save_repo = LocalFsSaveRepo(saves_dir=saves_dir)
    scenario_repo = LocalFsScenarioRepo(profile_dir=str(profile_dir))

    state = await init_game(
        "default",
        PlayerInput(name="테스터", race_id="human", gender="female"),
        save_repo,
        scenario_repo,
        locale="en",
    )
    assert state.locale == "en"

    reloaded = await save_repo.load_game(state.game_id)
    assert reloaded.locale == "en"


@pytest.mark.asyncio
async def test_init_game_default_locale_is_ko(tmp_path):
    """init_game with no locale arg defaults to 'ko'."""
    profile_dir = tmp_path / "profiles"
    saves_dir = str(tmp_path / "saves")
    _write_minimal_seed(profile_dir)
    save_repo = LocalFsSaveRepo(saves_dir=saves_dir)
    scenario_repo = LocalFsScenarioRepo(profile_dir=str(profile_dir))

    state = await init_game(
        "default",
        PlayerInput(name="테스터", race_id="human", gender="female"),
        save_repo,
        scenario_repo,
    )
    assert state.locale == "ko"


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
