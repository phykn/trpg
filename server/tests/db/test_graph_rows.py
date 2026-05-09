from src.db.graph_rows import graph_from_rows, graph_to_rows
from src.game.domain.graph import Graph, GraphEdge, GraphNode


def test_graph_rows_round_trip_nodes_edges_and_properties():
    graph = Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town"},
            ),
            "player": GraphNode(
                id="player",
                type="character",
                properties={"name": "Player"},
            ),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
                properties={"source": "test"},
            )
        },
    )

    node_rows, edge_rows = graph_to_rows("game-1", graph)

    node_rows_by_id = {row.node_id: row for row in node_rows}
    assert node_rows_by_id["town"].game_id == "game-1"
    assert node_rows_by_id["town"].node_type == "location"
    assert node_rows_by_id["town"].properties == {"name": "Town"}

    assert edge_rows[0].game_id == "game-1"
    assert edge_rows[0].edge_id == "located_at:player:town"
    assert edge_rows[0].edge_type == "located_at"
    assert edge_rows[0].from_node_id == "player"
    assert edge_rows[0].to_node_id == "town"
    assert edge_rows[0].properties == {"source": "test"}

    restored = graph_from_rows(node_rows, edge_rows)

    assert restored == graph


def test_graph_to_rows_serializes_properties_as_json_values():
    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"visited_location_ids": {"town"}},
            ),
            "town": GraphNode(id="town", type="location"),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
                properties={"tags": {"visible"}},
            )
        },
    )

    node_rows, edge_rows = graph_to_rows("game-1", graph)

    assert node_rows[0].properties["visited_location_ids"] == ["town"]
    assert edge_rows[0].properties["tags"] == ["visible"]
