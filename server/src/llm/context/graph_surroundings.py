from typing import Any

from src.game.domain.content import node_label, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph_character import graph_character_kind, is_visible_character
from src.game.domain.graph_query import (
    characters_at,
    edges_from,
    equipment_of,
    inventory_of,
    items_at,
    known_skills_of,
    location_of,
)
from src.game.runtime.state import GameRuntimeState


def build_graph_surroundings(runtime: GameRuntimeState) -> dict[str, Any]:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    location_id = location_of(graph, player_id)
    location = graph.nodes.get(location_id or "")

    return {
        "in_combat": runtime.progress.graph_combat_state is not None,
        "location": _location_payload(runtime, location),
        "entities": _entity_payloads(runtime, player_id, location_id),
        "inventory": _inventory_payloads(runtime, player_id),
        "equipment": _equipment_payloads(runtime, player_id),
        "skills": _skill_payloads(runtime, player_id),
        "merchants": [],
        "corpses": [],
    }


def _entity_payloads(
    runtime: GameRuntimeState,
    player_id: str,
    location_id: str | None,
) -> list[dict[str, str]]:
    if location_id is None:
        return []

    graph = runtime.graph_index
    entities: list[dict[str, str]] = []
    for character_id in characters_at(graph, location_id):
        node = graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if character_id != player_id and not is_visible_character(node):
            continue
        entity_type = (
            "player" if character_id == player_id else graph_character_kind(node)
        )
        entities.append(
            {
                "id": node.id,
                "name": node_label(runtime.content, node),
                "type": entity_type,
            }
        )

    location = graph.nodes.get(location_id)
    if location is not None and location.type == "location":
        for edge in edges_from(graph, location_id, "connects_to"):
            target = graph.nodes.get(edge.to_node_id)
            if target is None or target.type != "location":
                continue
            entities.append(
                {
                    "id": target.id,
                    "name": node_label(runtime.content, target),
                    "type": "connection",
                }
            )

    for item_id in items_at(graph, location_id):
        item = graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        entities.append(
            {"id": item.id, "name": node_label(runtime.content, item), "type": "item"}
        )

    return entities


def _inventory_payloads(
    runtime: GameRuntimeState,
    player_id: str,
) -> list[dict[str, str]]:
    graph = runtime.graph_index
    items: list[dict[str, str]] = []
    for item_id in inventory_of(graph, player_id):
        item = graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        items.append(
            {
                "id": item.id,
                "name": node_label(runtime.content, item),
                "kind": _kind(runtime, item),
            }
        )
    return items


def _equipment_payloads(
    runtime: GameRuntimeState,
    player_id: str,
) -> dict[str, dict | None]:
    graph = runtime.graph_index
    equipment: dict[str, dict | None] = {
        "weapon": None,
        "armor": None,
        "accessory": None,
    }
    for edge in equipment_of(graph, player_id):
        slot = edge.properties.get("slot")
        if slot not in equipment:
            continue
        item = graph.nodes.get(edge.to_node_id)
        if item is None or item.type != "item":
            continue
        equipment[slot] = {"id": item.id, "name": node_label(runtime.content, item)}
    return equipment


def _skill_payloads(
    runtime: GameRuntimeState,
    player_id: str,
) -> list[dict[str, str]]:
    graph = runtime.graph_index
    skills: list[dict[str, str]] = []
    for edge in known_skills_of(graph, player_id):
        skill = graph.nodes.get(edge.to_node_id)
        if skill is None or skill.type != "skill":
            continue
        skills.append(
            {
                "id": skill.id,
                "name": node_label(runtime.content, skill),
                "type": _optional_str(node_value(runtime.content, skill, "type"))
                or "skill",
            }
        )
    return skills


def _location_payload(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, str] | None:
    if node is None or node.type != "location":
        return None
    payload = {"id": node.id, "name": node_label(runtime.content, node)}
    description = node_value(runtime.content, node, "description")
    if isinstance(description, str) and description:
        payload["description"] = description
    return payload


def _kind(runtime: GameRuntimeState, node: GraphNode) -> str:
    return (
        _optional_str(node_value(runtime.content, node, "kind"))
        or _optional_str(node_value(runtime.content, node, "type"))
        or "item"
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
