from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    RemoveEdgeChange,
    SetNodePropertyChange,
)
from src.game.domain.graph_query import edges_from, location_of


class GraphMoveError(ValueError):
    pass


class GraphMoveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    moved_character_ids: list[str]
    destination_id: str


def plan_character_move(
    graph: Graph,
    character_id: str,
    destination_id: str,
    *,
    require_connection: bool = False,
) -> GraphMoveResult:
    _require_character(graph, character_id)
    _require_location(graph, destination_id)

    current_location_id = location_of(graph, character_id)
    if require_connection:
        _require_adjacent_destination(graph, character_id, current_location_id, destination_id)

    moved_ids = _character_and_companions(graph, character_id)
    changes: list[GraphChange] = []
    for moved_id in moved_ids:
        changes.extend(_move_one_character(graph, moved_id, destination_id))

    return GraphMoveResult(
        changes=changes,
        moved_character_ids=moved_ids,
        destination_id=destination_id,
    )


def _require_character(graph: Graph, character_id: str) -> None:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphMoveError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphMoveError(f"node is not a character: {character_id}")


def _require_location(graph: Graph, location_id: str) -> None:
    node = graph.nodes.get(location_id)
    if node is None:
        raise GraphMoveError(f"missing location: {location_id}")
    if node.type != "location":
        raise GraphMoveError(f"node is not a location: {location_id}")


def _require_adjacent_destination(
    graph: Graph,
    character_id: str,
    current_location_id: str | None,
    destination_id: str,
) -> None:
    if current_location_id is None:
        raise GraphMoveError(f"missing current location: {character_id}")
    if current_location_id == destination_id:
        return
    reachable = sorted(
        edge.to_node_id for edge in edges_from(graph, current_location_id, "connects_to")
    )
    if destination_id not in reachable:
        raise GraphMoveError(
            f"destination {destination_id!r} is not adjacent to current "
            f"location {current_location_id!r}. Reachable: {reachable}."
        )


def _character_and_companions(graph: Graph, character_id: str) -> list[str]:
    companion_ids = [
        edge.to_node_id for edge in edges_from(graph, character_id, "has_companion")
    ]
    return [character_id, *companion_ids]


def _move_one_character(
    graph: Graph,
    character_id: str,
    destination_id: str,
) -> list[GraphChange]:
    changes: list[GraphChange] = []
    existing_location_edges = edges_from(graph, character_id, "located_at")
    already_at_destination = any(
        edge.to_node_id == destination_id for edge in existing_location_edges
    )

    if not already_at_destination:
        for edge in existing_location_edges:
            changes.append(RemoveEdgeChange(type="remove_edge", edge_id=edge.id))
        changes.append(
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=f"located_at:{character_id}:{destination_id}",
                    type="located_at",
                    from_node_id=character_id,
                    to_node_id=destination_id,
                ),
            )
        )

    changes.append(
        SetNodePropertyChange(
            type="set_node_property",
            node_id=character_id,
            path="visited_location_ids",
            value=_visited_with(graph, character_id, destination_id),
        )
    )
    return changes


def _visited_with(graph: Graph, character_id: str, destination_id: str) -> list[str]:
    raw = graph.nodes[character_id].properties.get("visited_location_ids", [])
    if not isinstance(raw, list):
        raw = []
    visited = {item for item in raw if isinstance(item, str)}
    visited.add(destination_id)
    return sorted(visited)
