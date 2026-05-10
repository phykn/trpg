from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType


class GraphNodeRow(BaseModel):
    game_id: str
    node_id: str
    node_type: NodeType
    properties: dict[str, Any]


class GraphEdgeRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    game_id: str
    edge_id: str
    edge_type: EdgeType
    from_node_id: str
    to_node_id: str
    properties: dict[str, Any]


def _json_properties(model: GraphNode | GraphEdge) -> dict[str, Any]:
    return model.model_dump(mode="json")["properties"]


def graph_to_rows(
    game_id: str,
    graph: Graph,
) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    return (
        graph_node_rows(game_id, graph, graph.nodes.keys()),
        graph_edge_rows(game_id, graph, graph.edges.keys()),
    )


def graph_node_rows(
    game_id: str,
    graph: Graph,
    node_ids,
) -> list[GraphNodeRow]:
    return [
        GraphNodeRow(
            game_id=game_id,
            node_id=node.id,
            node_type=node.type,
            properties=_json_properties(node),
        )
        for node_id in node_ids
        if (node := graph.nodes.get(node_id)) is not None
    ]


def graph_edge_rows(
    game_id: str,
    graph: Graph,
    edge_ids,
) -> list[GraphEdgeRow]:
    return [
        GraphEdgeRow(
            game_id=game_id,
            edge_id=edge.id,
            edge_type=edge.type,
            from_node_id=edge.from_node_id,
            to_node_id=edge.to_node_id,
            properties=_json_properties(edge),
        )
        for edge_id in edge_ids
        if (edge := graph.edges.get(edge_id)) is not None
    ]


def graph_from_rows(
    node_rows: list[GraphNodeRow],
    edge_rows: list[GraphEdgeRow],
) -> Graph:
    nodes = {
        row.node_id: GraphNode(
            id=row.node_id,
            type=row.node_type,
            properties=row.properties,
        )
        for row in node_rows
    }
    edges = {
        row.edge_id: GraphEdge(
            id=row.edge_id,
            type=row.edge_type,
            from_node_id=row.from_node_id,
            to_node_id=row.to_node_id,
            properties=row.properties,
        )
        for row in edge_rows
    }
    return Graph(nodes=nodes, edges=edges)
