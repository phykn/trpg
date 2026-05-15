import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_change
from src.game.engines.graph.move import GraphMoveError, plan_character_move


def _graph() -> Graph:
    return Graph(
        nodes={
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"visited_location_ids": ["town"]},
            ),
            "companion_01": GraphNode(
                id="companion_01",
                type="character",
                properties={"visited_location_ids": ["town"]},
            ),
            "town": GraphNode(id="town", type="location"),
            "forest": GraphNode(id="forest", type="location"),
            "tower": GraphNode(id="tower", type="location"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:companion_01:town": GraphEdge(
                id="located_at:companion_01:town",
                type="located_at",
                from_node_id="companion_01",
                to_node_id="town",
            ),
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
            "has_companion:player_01:companion_01": GraphEdge(
                id="has_companion:player_01:companion_01",
                type="has_companion",
                from_node_id="player_01",
                to_node_id="companion_01",
            ),
        },
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_move_replaces_location_edge_and_marks_visited():
    result = plan_character_move(
        _graph(),
        "player_01",
        "forest",
        require_connection=True,
    )
    changed = _apply_all(_graph(), result.changes)

    assert result.moved_character_ids == ["player_01", "companion_01"]
    assert changed.edges["located_at:player_01:forest"].to_node_id == "forest"
    assert "located_at:player_01:town" not in changed.edges
    assert changed.nodes["player_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]


def test_companion_follow_moves_companion_and_marks_visited():
    result = plan_character_move(
        _graph(),
        "player_01",
        "forest",
        require_connection=True,
    )
    changed = _apply_all(_graph(), result.changes)

    assert changed.edges["located_at:companion_01:forest"].to_node_id == "forest"
    assert "located_at:companion_01:town" not in changed.edges
    assert changed.nodes["companion_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]


def test_non_adjacent_move_is_rejected_when_connection_required():
    with pytest.raises(GraphMoveError, match="not adjacent"):
        plan_character_move(_graph(), "player_01", "tower", require_connection=True)


def test_npc_move_can_skip_adjacency_gate():
    graph = _graph()
    result = plan_character_move(graph, "companion_01", "tower")
    changed = _apply_all(graph, result.changes)

    assert changed.edges["located_at:companion_01:tower"].to_node_id == "tower"


def test_missing_character_or_destination_is_rejected():
    with pytest.raises(GraphMoveError, match="missing character"):
        plan_character_move(_graph(), "ghost", "forest")
    with pytest.raises(GraphMoveError, match="missing location"):
        plan_character_move(_graph(), "player_01", "void")


def test_move_result_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_character_move(graph, "player_01", "forest", require_connection=True)

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]
