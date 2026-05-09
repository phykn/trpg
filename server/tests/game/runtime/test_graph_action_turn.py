import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.turn import GraphActionTurnError, run_graph_action_turn


def _character(
    character_id: str,
    *,
    hp: int = 30,
    max_hp: int = 30,
    mp: int = 10,
    max_mp: int = 10,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": hp,
            "max_hp": max_hp,
            "mp": mp,
            "max_mp": max_mp,
            "alive": hp > 0,
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
            "status": [],
            "visited_location_ids": [],
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
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "Forest"},
            ),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01", hp=24, max_hp=24),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:goblin_01:town": GraphEdge(
                id="located_at:goblin_01:town",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town",
            ),
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_run_graph_action_turn_saves_move_and_returns_front_state(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(repo, "game-1", Action(verb="move", to="forest"))
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert "located_at:player_01:forest" in saved_graph.edges
    assert "located_at:player_01:town" not in saved_graph.edges
    assert saved_progress.turn_count == 1
    assert saved_progress.next_log_id == 2
    assert len(saved_logs) == 1
    assert saved_logs[0].kind == "act"
    assert saved_logs[0].text == "당신은 Forest로 이동합니다."
    assert result.front_state.log == saved_logs
    assert result.front_state.place.id == "forest"
    assert result.runtime.progress.turn_count == 1


async def test_run_graph_action_turn_saves_attack_progress_and_front_combat(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    saved_progress = await repo.load_progress("game-1")

    assert saved_progress.graph_combat_state is not None
    assert saved_progress.graph_combat_state.round == 2
    assert result.front_state.combat is not None
    assert result.front_state.combat.round == 2


async def test_run_graph_action_turn_rejects_query_without_saving(tmp_path):
    repo = await _repo(tmp_path)

    with pytest.raises(GraphActionTurnError, match="read-only"):
        await run_graph_action_turn(repo, "game-1", Action(verb="query", what="status"))

    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    assert saved_graph == _graph()
    assert saved_progress.turn_count == 0
