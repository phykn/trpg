import json
import tempfile
from pathlib import Path

import pytest

from src.domain.entities import Character, Stats
from src.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.domain.errors import PersistenceFailed, ProfileNotFound, RaceNotFound
from src.persistence.init import PlayerInput, init_game
from src.domain.state import GameState
from src.persistence.store import (
    append_dialogue_entries,
    append_history_entries,
    append_log_entries,
    load_game,
    read_current_game_id,
    save_full,
    save_meta,
    write_current_game_id,
)


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_game_state_round_trip(fresh_state):
    fresh_state.characters["p"] = Character(
        id="p", name="x", race_id="human", stats=Stats()
    )
    fresh_state.log_entries.append(GMLogEntry(id=1, kind="gm", text="hi"))
    dumped = fresh_state.model_dump_json()
    restored = GameState.model_validate_json(dumped)
    assert restored.characters["p"].name == "x"
    assert restored.log_entries[0].kind == "gm"


async def test_save_full_creates_directory_layout(fresh_state, tmp_data):
    fresh_state.characters["p"] = Character(
        id="p", name="x", race_id="human", stats=Stats()
    )
    await save_full(fresh_state, tmp_data)
    gdir = Path(tmp_data) / "games" / fresh_state.game_id
    assert (gdir / "meta.json").exists()
    assert (gdir / "characters" / "p.json").exists()
    # Empty kinds may or may not have a dir — the point is that no files are written.
    assert not (gdir / "items").exists() or not list((gdir / "items").glob("*.json"))


async def test_save_load_round_trip_through_disk(fresh_state, tmp_data):
    fresh_state.characters["p"] = Character(
        id="p", name="주", race_id="human", stats=Stats()
    )
    fresh_state.log_entries.append(GMLogEntry(id=1, kind="gm", text="처음"))
    fresh_state.turn_log.append(TurnLogEntry(turn=1, summary="요약"))
    fresh_state.recent_dialogue.append(DialoguePair(turn=1, player="p", narrator="n"))
    fresh_state.next_log_id = 2

    await save_full(fresh_state, tmp_data)
    await append_log_entries(tmp_data, fresh_state.game_id, fresh_state.log_entries)
    await append_history_entries(tmp_data, fresh_state.game_id, fresh_state.turn_log)
    await append_dialogue_entries(
        tmp_data, fresh_state.game_id, fresh_state.recent_dialogue
    )

    loaded = load_game(tmp_data, fresh_state.game_id)
    assert loaded.game_id == fresh_state.game_id
    assert loaded.characters["p"].name == "주"
    assert loaded.next_log_id == 2
    assert loaded.log_entries[0].kind == "gm"
    assert loaded.log_entries[0].text == "처음"
    assert loaded.turn_log[0].summary == "요약"
    assert loaded.recent_dialogue[0].player == "p"


async def test_combat_state_survives_meta_round_trip(fresh_state, tmp_data):
    # Regression: meta.json used to skip combat_state, so each /turn request
    # reloaded as combat-cleared and the engine restarted the fight every turn,
    # never letting the player land more than the opening hit.
    from src.domain.state import CombatState
    fresh_state.combat_state = CombatState(
        round=2,
        turn_order=("player_01", "goblin_01"),
        current_turn=1,
        enemy_ids=("goblin_01",),
    )
    await save_full(fresh_state, tmp_data)
    loaded = load_game(tmp_data, fresh_state.game_id)
    assert loaded.combat_state is not None
    assert loaded.combat_state.round == 2
    assert tuple(loaded.combat_state.turn_order) == ("player_01", "goblin_01")
    assert loaded.combat_state.current_turn == 1
    assert tuple(loaded.combat_state.enemy_ids) == ("goblin_01",)


async def test_jsonl_appends_are_cumulative(fresh_state, tmp_data):
    await save_full(fresh_state, tmp_data)
    await append_log_entries(
        tmp_data,
        fresh_state.game_id,
        [
            GMLogEntry(id=1, kind="gm", text="첫번째"),
        ],
    )
    await append_log_entries(
        tmp_data,
        fresh_state.game_id,
        [
            GMLogEntry(id=2, kind="gm", text="두번째"),
        ],
    )
    loaded = load_game(tmp_data, fresh_state.game_id)
    assert [e.text for e in loaded.log_entries] == ["첫번째", "두번째"]


def test_load_missing_raises_filenotfound(tmp_data):
    with pytest.raises(FileNotFoundError):
        load_game(tmp_data, "nope")


async def test_save_to_unwritable_path_raises_persistence_failed(fresh_state):
    with pytest.raises(PersistenceFailed):
        await save_meta(fresh_state, "/proc/no_such_writable")


async def test_current_game_id_lifecycle(tmp_data):
    assert read_current_game_id(tmp_data) is None
    await write_current_game_id(tmp_data, "abc-123")
    assert read_current_game_id(tmp_data) == "abc-123"


def _write_minimal_seed(profile_dir: Path) -> None:
    pdir = profile_dir / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(
        json.dumps(
            {
                "start_location_id": "plaza_01",
                "world_time": "0812-04-28T12:00:00",
            }
        ),
        encoding="utf-8",
    )
    (pdir / "player_template.json").write_text(
        json.dumps({"id": "player_01"}), encoding="utf-8"
    )
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(
        json.dumps(
            {
                "id": "human",
                "name": "인간",
                "description": "x",
                "racial_skills": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "locations").mkdir()
    (pdir / "locations" / "plaza.json").write_text(
        json.dumps(
            {
                "id": "plaza_01",
                "name": "광장",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


async def test_init_game_happy_path(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    saves_dir = str(Path(tmp_data) / "saves")
    _write_minimal_seed(profile_dir)
    state = await init_game(
        "default",
        PlayerInput(name="테스터", race_id="human", appearance="외형"),
        saves_dir,
        str(profile_dir),
    )
    assert state.profile == "default"
    assert state.player_id == "player_01"
    p = state.characters["player_01"]
    assert p.name == "테스터" and p.race_id == "human"
    assert p.stats.STR == 10 and p.max_hp == 20  # level 0 formula
    assert read_current_game_id(saves_dir) == state.game_id

    # Seed files were copied into the game folder.
    gdir = Path(saves_dir) / "games" / state.game_id
    assert (gdir / "meta.json").exists()
    assert (gdir / "characters" / "player_01.json").exists()
    assert (gdir / "races" / "human.json").exists()
    assert (gdir / "locations" / "plaza.json").exists()

    # Round-trip via reload.
    reloaded = load_game(saves_dir, state.game_id)
    assert reloaded.characters["player_01"].name == "테스터"
    assert reloaded.locations["plaza_01"].name == "광장"


async def test_init_game_unknown_profile(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    profile_dir.mkdir()
    with pytest.raises(ProfileNotFound):
        await init_game(
            "missing",
            PlayerInput(name="x", race_id="human", appearance="y"),
            tmp_data,
            str(profile_dir),
        )


async def test_init_game_unknown_race(tmp_data):
    profile_dir = Path(tmp_data) / "profiles"
    _write_minimal_seed(profile_dir)
    with pytest.raises(RaceNotFound):
        await init_game(
            "default",
            PlayerInput(name="x", race_id="dragon", appearance="y"),
            tmp_data,
            str(profile_dir),
        )
