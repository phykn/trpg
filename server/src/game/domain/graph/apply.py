from typing import Any

from pydantic import TypeAdapter

from .models import (
    AddEdgeChange,
    AddNodeChange,
    Graph,
    GraphChange,
    GraphInvariantError,
    RemoveEdgeChange,
    SetEdgePropertyChange,
    SetNodePropertyChange,
)
from .validation import validate_graph


_GRAPH_CHANGE_ADAPTER = TypeAdapter(GraphChange)


def parse_graph_change(data: Any) -> GraphChange:
    return _GRAPH_CHANGE_ADAPTER.validate_python(data)


def apply_graph_change(graph: Graph, change: GraphChange) -> Graph:
    return apply_graph_changes(graph, [change])


def apply_graph_changes(graph: Graph, changes: list[GraphChange]) -> Graph:
    next_graph = graph.model_copy(deep=True)

    for change in changes:
        _apply_graph_change_in_place(next_graph, change)
    validate_graph(next_graph)
    return next_graph


def _apply_graph_change_in_place(graph: Graph, change: GraphChange) -> None:
    if isinstance(change, AddNodeChange):
        if change.node.id in graph.nodes:
            raise GraphInvariantError(f"duplicate node: {change.node.id}")
        graph.nodes[change.node.id] = change.node
    elif isinstance(change, SetNodePropertyChange):
        node = graph.nodes.get(change.node_id)
        if node is None:
            raise GraphInvariantError(f"missing node: {change.node_id}")
        _set_property(node.properties, change.path, change.value)
    elif isinstance(change, AddEdgeChange):
        if change.edge.id in graph.edges:
            raise GraphInvariantError(f"duplicate edge: {change.edge.id}")
        graph.edges[change.edge.id] = change.edge
    elif isinstance(change, SetEdgePropertyChange):
        edge = graph.edges.get(change.edge_id)
        if edge is None:
            raise GraphInvariantError(f"missing edge: {change.edge_id}")
        _set_property(edge.properties, change.path, change.value)
    elif isinstance(change, RemoveEdgeChange):
        if change.edge_id not in graph.edges:
            raise GraphInvariantError(f"missing edge: {change.edge_id}")
        del graph.edges[change.edge_id]


def _set_property(properties: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise GraphInvariantError("empty property path")

    current = properties
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value
