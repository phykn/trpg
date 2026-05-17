import json
from pathlib import Path

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress


def _graph() -> Graph:
    return Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"name": "Player"},
            ),
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town"},
            ),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            )
        },
    )


async def test_local_fs_graph_repo_round_trips_graph_and_progress(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = _graph()
    progress = GameProgress(game_id="game-1", player_id="player", turn_count=2)

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)

    assert await repo.load_graph("game-1") == graph
    assert await repo.load_progress("game-1") == progress


async def test_local_fs_graph_repo_raises_for_missing_game(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await repo.load_graph("missing")

    with pytest.raises(FileNotFoundError):
        await repo.load_progress("missing")


async def test_local_fs_graph_repo_wraps_invalid_graph(tmp_path):
    graph_dir = Path(tmp_path) / "games" / "game-1" / "graph"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.json").write_text(
        json.dumps(
            [
                {
                    "game_id": "game-1",
                    "node_id": "player",
                    "node_type": "character",
                    "properties": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    (graph_dir / "edges.json").write_text(
        json.dumps(
            [
                {
                    "game_id": "game-1",
                    "edge_id": "located_at:player:void",
                    "edge_type": "located_at",
                    "from_node_id": "player",
                    "to_node_id": "void",
                    "properties": {},
                }
            ]
        ),
        encoding="utf-8",
    )

    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(PersistenceFailed, match="missing node"):
        await repo.load_graph("game-1")
