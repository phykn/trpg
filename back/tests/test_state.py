import json
import tempfile
from pathlib import Path

import pytest

from src.domain.entities import Character, Stats
from src.domain.memory import GMLogEntry
from src.errors import PersistenceFailed, ProfileNotFound, RaceNotFound
from src.state.init import PlayerInput, init_game
from src.state.models import GameState
from src.state.store import (
    load_game,
    read_current_game_id,
    save_game,
    write_current_game_id,
)


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_game_state_round_trip(fresh_state):
    fresh_state.characters["p"] = Character(id="p", name="x", race_id="human", stats=Stats())
    fresh_state.log_entries.append(GMLogEntry(id=1, kind="gm", text="hi"))
    dumped = fresh_state.model_dump_json()
    restored = GameState.model_validate_json(dumped)
    assert restored.characters["p"].name == "x"
    assert restored.log_entries[0].kind == "gm"


async def test_atomic_save_and_load(fresh_state, tmp_data):
    await save_game(fresh_state, tmp_data)
    p = Path(tmp_data) / "games" / f"{fresh_state.game_id}.json"
    assert p.exists()
    assert not p.with_suffix(".json.tmp").exists()
    loaded = load_game(tmp_data, fresh_state.game_id)
    assert loaded.game_id == fresh_state.game_id


def test_load_missing_raises_filenotfound(tmp_data):
    with pytest.raises(FileNotFoundError):
        load_game(tmp_data, "nope")


async def test_save_to_unwritable_path_raises_persistence_failed(fresh_state):
    with pytest.raises(PersistenceFailed):
        await save_game(fresh_state, "/proc/no_such_writable")


async def test_current_game_id_lifecycle(tmp_data):
    assert read_current_game_id(tmp_data) is None
    await write_current_game_id(tmp_data, "abc-123")
    assert read_current_game_id(tmp_data) == "abc-123"


def _write_minimal_seed(profile_dir: Path) -> None:
    pdir = profile_dir / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(json.dumps({
        "start_location_id": "plaza_01",
        "world_time": "0812-04-28T12:00:00",
    }), encoding="utf-8")
    (pdir / "player_template.json").write_text(json.dumps({"id": "player_01"}), encoding="utf-8")
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(json.dumps({
        "id": "human", "name": "인간", "description": "x", "racial_skills": [],
    }, ensure_ascii=False), encoding="utf-8")
    (pdir / "locations").mkdir()
    (pdir / "locations" / "plaza.json").write_text(json.dumps({
        "id": "plaza_01", "name": "광장",
    }, ensure_ascii=False), encoding="utf-8")


async def test_init_game_happy_path(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    data_dir = str(Path(tmp_data) / "data")
    _write_minimal_seed(profile_dir)
    state = await init_game(
        "default",
        PlayerInput(name="테스터", race_id="human", appearance="외형"),
        data_dir, str(profile_dir),
    )
    assert state.profile == "default"
    assert state.player_id == "player_01"
    p = state.characters["player_01"]
    assert p.name == "테스터" and p.race_id == "human"
    assert p.stats.STR == 10 and p.max_hp == 20  # level 0 공식
    assert read_current_game_id(data_dir) == state.game_id


async def test_init_game_unknown_profile(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    profile_dir.mkdir()
    with pytest.raises(ProfileNotFound):
        await init_game("missing", PlayerInput(name="x", race_id="human", appearance="y"),
                        tmp_data, str(profile_dir))


async def test_init_game_unknown_race(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    _write_minimal_seed(profile_dir)
    with pytest.raises(RaceNotFound):
        await init_game("default", PlayerInput(name="x", race_id="dragon", appearance="y"),
                        tmp_data, str(profile_dir))
