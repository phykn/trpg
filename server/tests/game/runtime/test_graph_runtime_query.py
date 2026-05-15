from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.confirmation import run_graph_action_request
from src.game.runtime.action.query import answer_graph_query
from src.game.runtime.state import GameRuntimeState


def _character(character_id: str, name: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": name,
            "hp": 20,
            "max_hp": 30,
            "mp": 5,
            "max_mp": 10,
            "alive": True,
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "마을"},
            ),
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "숲"},
            ),
            "player_01": _character("player_01", "주인공"),
            "goblin_01": _character("goblin_01", "고블린"),
            "hidden_01": _character("hidden_01", "숨은 자"),
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
            "hidden_at:hidden_01:town": GraphEdge(
                id="hidden_at:hidden_01:town",
                type="hidden_at",
                from_node_id="hidden_01",
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


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=_graph(),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


def test_answer_graph_query_surroundings_uses_visible_graph_facts():
    answer = answer_graph_query(
        _runtime(),
        Action(verb="query", what="surroundings"),
    )

    assert "마을" in answer
    assert "고블린" in answer
    assert "숨은 자" not in answer


async def test_graph_query_request_answers_without_advancing_turn(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="query", what="exits"),
    )
    saved_progress = await repo.load_progress("game-1")

    assert result.status == "answered"
    assert "숲" in result.message
    assert saved_progress.turn_count == 0
    assert saved_progress.pending_confirmation is None
