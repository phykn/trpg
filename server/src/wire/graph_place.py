from __future__ import annotations

from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_character import graph_character_kind, is_visible_character
from src.game.domain.graph_query import characters_at, edges_from, location_of
from src.wire.graph_payload_helpers import node_name, optional_str, require_node, resource
from src.wire.models import GraphPlaceLinkPayload, GraphPlacePayload, GraphPlaceTargetPayload


def place_payload(graph: Graph, player_id: str) -> GraphPlacePayload | None:
    location_id = location_of(graph, player_id)
    if location_id is None:
        return None
    location = graph.nodes.get(location_id)
    if location is None or location.type != "location":
        return None

    exits: list[GraphPlaceLinkPayload] = []
    for edge in edges_from(graph, location_id, "connects_to"):
        target = graph.nodes.get(edge.to_node_id)
        if target is None or target.type != "location":
            continue
        exits.append(_place_link(target))

    targets: list[GraphPlaceTargetPayload] = []
    for character_id in characters_at(graph, location_id):
        if character_id == player_id:
            continue
        target = require_node(graph, character_id, "character")
        if not is_visible_character(target):
            continue
        targets.append(
            GraphPlaceTargetPayload(
                id=target.id,
                name=node_name(target),
                kind=graph_character_kind(target),
                hp=resource(target, "hp", "max_hp"),
            )
        )

    return GraphPlacePayload(
        id=location.id,
        name=node_name(location),
        description=optional_str(location.properties.get("description")) or "",
        exits=exits,
        targets=targets,
    )


def _place_link(location: GraphNode) -> GraphPlaceLinkPayload:
    return GraphPlaceLinkPayload(
        id=location.id,
        name=node_name(location),
        description=optional_str(location.properties.get("description")) or "",
    )
