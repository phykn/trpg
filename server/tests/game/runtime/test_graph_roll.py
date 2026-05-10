import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.confirmation import run_graph_action_request
from src.game.runtime.roll import GraphRollExpected, run_graph_roll, start_graph_roll


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": 30,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "alive": True,
            "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town"},
            ),
            "player_01": _character("player_01"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_start_graph_roll_stores_pending_roll_without_log(tmp_path):
    repo = await _repo(tmp_path)

    result = await start_graph_roll(
        repo,
        "game-1",
        Action(verb="perceive", what="town"),
    )
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert progress.pending_roll["title"] == "지력 판정이 필요합니다"
    assert progress.pending_roll["required_roll"] == 13
    assert logs == []


async def test_graph_action_request_perceive_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="perceive", what="town"),
    )
    progress = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert result.front_state.pending_roll is not None


async def test_run_graph_roll_resolves_pending_roll_and_appends_roll_log(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert progress.pending_roll is None
    assert progress.turn_count == 1
    assert logs[0].kind == "roll"
    assert logs[0].check == "지력"
    assert logs[0].roll == 13
    assert logs[0].result == "success"
    assert result.front_state.pending_roll is None


async def test_run_graph_roll_requires_matching_pending_id(tmp_path):
    repo = await _repo(tmp_path)

    with pytest.raises(GraphRollExpected):
        await run_graph_roll(repo, "game-1", "missing", dice=13)
