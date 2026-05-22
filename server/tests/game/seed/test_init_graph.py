import json
from pathlib import Path

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.db.scenario.local_fs import LocalFsScenarioRepo
from src.game.domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from src.game.seed.init_graph import init_graph_game
from src.game.seed.player import PlayerInput


def _write_seed(root: Path) -> None:
    pdir = root / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(
        json.dumps({"start_location": "town"}),
        encoding="utf-8",
    )
    (pdir / "player.json").write_text(
        json.dumps({"id": "player_01"}),
        encoding="utf-8",
    )
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(
        json.dumps(
            {"id": "human", "name": "인간", "description": ""},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "locations").mkdir()
    (pdir / "locations" / "town.json").write_text(
        json.dumps({"id": "town", "name": "마을"}, ensure_ascii=False),
        encoding="utf-8",
    )


async def test_init_graph_game_persists_graph_and_progress(tmp_path):
    profiles = tmp_path / "profiles"
    saves = tmp_path / "saves"
    _write_seed(profiles)

    repo = LocalFsGraphRepo(str(saves))
    bundle = await init_graph_game(
        "default",
        PlayerInput(name="테스터", race_id="human", gender="female"),
        repo,
        LocalFsScenarioRepo(str(profiles)),
        locale="ko",
    )

    loaded_graph = await repo.load_graph(bundle.progress.game_id)
    loaded_progress = await repo.load_progress(bundle.progress.game_id)

    assert loaded_graph == bundle.graph
    assert loaded_progress == bundle.progress
    assert loaded_graph.nodes["player_01"].properties["name"] == "테스터"
    assert bundle.content.world_guidance == "world"


async def test_init_graph_game_unknown_profile(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()

    with pytest.raises(ProfileNotFound):
        await init_graph_game(
            "missing",
            PlayerInput(name="테스터", race_id="human", gender="female"),
            LocalFsGraphRepo(str(tmp_path / "saves")),
            LocalFsScenarioRepo(str(profiles)),
        )


async def test_init_graph_game_unknown_race(tmp_path):
    profiles = tmp_path / "profiles"
    _write_seed(profiles)

    with pytest.raises(RaceNotFound):
        await init_graph_game(
            "default",
            PlayerInput(name="테스터", race_id="dragon", gender="female"),
            LocalFsGraphRepo(str(tmp_path / "saves")),
            LocalFsScenarioRepo(str(profiles)),
        )


async def test_init_graph_game_rejects_malformed_seed(tmp_path):
    profiles = tmp_path / "profiles"
    _write_seed(profiles)
    (profiles / "default" / "start.json").write_text(
        json.dumps({"start_location": "missing"}),
        encoding="utf-8",
    )

    with pytest.raises(ProfileMalformed, match="start_location"):
        await init_graph_game(
            "default",
            PlayerInput(name="테스터", race_id="human", gender="female"),
            LocalFsGraphRepo(str(tmp_path / "saves")),
            LocalFsScenarioRepo(str(profiles)),
        )
