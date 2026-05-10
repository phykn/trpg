import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.progress import GameProgress
from src.game.engines.growth import calc_max_hp, calc_max_mp, xp_for_next_level
from src.game.runtime.level_up import GraphLevelUpError, run_graph_level_up


def _player(*, xp_pool: int | None = None) -> GraphNode:
    level = 1
    stats = {"body": 10, "agility": 10, "mind": 10, "presence": 10}
    return GraphNode(
        id="player_01",
        type="character",
        properties={
            "name": "테스터",
            "level": level,
            "xp_pool": xp_for_next_level(level) if xp_pool is None else xp_pool,
            "gold": 0,
            "hp": 12,
            "max_hp": calc_max_hp(level, stats["body"]),
            "mp": 4,
            "max_mp": calc_max_mp(level, stats["mind"]),
            "alive": True,
            "stats": stats,
            "status": [],
        },
    )


async def _repo(tmp_path, *, xp_pool: int | None = None) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph(
        "game-1", Graph(nodes={"player_01": _player(xp_pool=xp_pool)})
    )
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_run_graph_level_up_commits_choice_and_returns_front_state(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_level_up(repo, "game-1", stat_up="body", skill_id=None)
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["stats"] == {"body": 11, "agility": 10, "mind": 10, "presence": 10}
    assert player["max_hp"] == calc_max_hp(2, 11)
    assert player["max_mp"] == calc_max_mp(2, 10)
    assert saved_progress.next_log_id == 2
    assert len(saved_logs) == 1
    assert saved_logs[0].kind == "act"
    assert (
        saved_logs[0].text
        == "테스터의 레벨이 올랐습니다 (레벨 2, 몸 ↑, HP 35 / MP 25)."
    )
    assert result.front_state.hero.level == 2
    assert result.front_state.hero.exp == 0
    assert result.front_state.log == saved_logs


async def test_run_graph_level_up_rejects_insufficient_xp_without_saving(tmp_path):
    repo = await _repo(tmp_path, xp_pool=0)

    with pytest.raises(GraphLevelUpError, match="not enough xp"):
        await run_graph_level_up(repo, "game-1", stat_up="body", skill_id=None)

    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")
    assert saved_graph.nodes["player_01"].properties["level"] == 1
    assert saved_progress.next_log_id == 1
    assert saved_logs == []
