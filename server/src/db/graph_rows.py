from __future__ import annotations

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
    node_rows = [
        GraphNodeRow(
            game_id=game_id,
            node_id=node.id,
            node_type=node.type,
            properties=_json_properties(node),
        )
        for node in graph.nodes.values()
    ]
    edge_rows = [
        GraphEdgeRow(
            game_id=game_id,
            edge_id=edge.id,
            edge_type=edge.type,
            from_node_id=edge.from_node_id,
            to_node_id=edge.to_node_id,
            properties=_json_properties(edge),
        )
        for edge in graph.edges.values()
    ]
    return node_rows, edge_rows


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
