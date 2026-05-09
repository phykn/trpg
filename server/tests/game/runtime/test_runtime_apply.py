import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.apply import (
    GraphRuntimeApplyError,
    apply_runtime_graph_changes,
)


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player": GraphNode(
                    id="player",
                    type="character",
                    properties={"hp": 5},
                ),
                "town": GraphNode(id="town", type="location"),
                "forest": GraphNode(id="forest", type="location"),
            },
            edges={
                "located_at:player:town": GraphEdge(
                    id="located_at:player:town",
                    type="located_at",
                    from_node_id="player",
                    to_node_id="town",
                )
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player"),
    )


def test_apply_raw_dict_batch_returns_new_runtime_and_touched_ids():
    runtime = _runtime()

    result = apply_runtime_graph_changes(
        runtime,
        [
            {
                "type": "set_node_property",
                "node_id": "player",
                "path": "hp",
                "value": 8,
            },
            {"type": "remove_edge", "edge_id": "located_at:player:town"},
            {
                "type": "add_edge",
                "edge": {
                    "id": "located_at:player:forest",
                    "type": "located_at",
                    "from": "player",
                    "to": "forest",
                },
            },
        ],
    )

    assert result.applied == 3
    assert result.changed_node_ids == ["player"]
    assert result.changed_edge_ids == [
        "located_at:player:forest",
        "located_at:player:town",
    ]
    assert result.runtime.graph.nodes["player"].properties["hp"] == 8
    assert "located_at:player:forest" in result.runtime.graph.edges


def test_apply_does_not_mutate_original_runtime():
    runtime = _runtime()

    result = apply_runtime_graph_changes(
        runtime,
        [
            {
                "type": "set_node_property",
                "node_id": "player",
                "path": "hp",
                "value": 8,
            }
        ],
    )

    assert runtime.graph.nodes["player"].properties["hp"] == 5
    assert result.runtime is not runtime
    assert result.runtime.graph is not runtime.graph


def test_invalid_later_change_raises_and_original_runtime_stays_unchanged():
    runtime = _runtime()

    with pytest.raises(GraphRuntimeApplyError, match="missing node"):
        apply_runtime_graph_changes(
            runtime,
            [
                {
                    "type": "set_node_property",
                    "node_id": "player",
                    "path": "hp",
                    "value": 8,
                },
                {
                    "type": "add_edge",
                    "edge": {
                        "id": "located_at:ghost:forest",
                        "type": "located_at",
                        "from": "ghost",
                        "to": "forest",
                    },
                },
            ],
        )

    assert runtime.graph.nodes["player"].properties["hp"] == 5
    assert "located_at:ghost:forest" not in runtime.graph.edges


def test_invalid_raw_change_shape_raises_runtime_apply_error():
    with pytest.raises(GraphRuntimeApplyError, match="type"):
        apply_runtime_graph_changes(_runtime(), [{"type": "unknown_change"}])
