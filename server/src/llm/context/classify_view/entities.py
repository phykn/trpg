from __future__ import annotations

from typing import Any

from src.game.domain.content import node_label, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import graph_character_kind, is_visible_character
from src.game.domain.graph.query import (
    characters_at,
    edges_from,
    equipment_of,
    inventory_of,
    items_at,
    known_skills_of,
)
from src.game.runtime.state import GameRuntimeState


def visible_targets(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for character_id in characters_at(runtime.graph_index, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        payload: dict[str, Any] = {
            "id": node.id,
            "name": node_label(runtime.content, node),
            "type": graph_character_kind(node),
        }
        if node.properties.get("protected") is True:
            payload["protected"] = True
        out.append(payload)
    return out


def exits(runtime: GameRuntimeState, location_id: str | None) -> list[dict[str, str]]:
    if location_id is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, location_id, "connects_to"):
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "location":
            out.append({"id": node.id, "name": node_label(runtime.content, node)})
    return out


def inventory(runtime: GameRuntimeState, player_id: str) -> list[dict[str, Any]]:
    return inventory_for_owner(runtime, player_id)


def inventory_for_owner(
    runtime: GameRuntimeState,
    owner_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, owner_id):
        node = runtime.graph.nodes.get(item_id)
        if node is None or node.type != "item":
            continue
        out.append(item_payload(runtime, node))
    return out


def equipment(
    runtime: GameRuntimeState,
    player_id: str,
) -> dict[str, dict[str, str] | None]:
    out: dict[str, dict[str, str] | None] = {
        "weapon": None,
        "armor": None,
        "accessory": None,
    }
    for edge in equipment_of(runtime.graph_index, player_id):
        slot = edge.properties.get("slot")
        if slot not in out:
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "item":
            out[slot] = {"id": node.id, "name": node_label(runtime.content, node)}
    return out


def skills(runtime: GameRuntimeState, player_id: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for edge in known_skills_of(runtime.graph_index, player_id):
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "skill":
            payload = {"id": node.id, "name": node_label(runtime.content, node)}
            action = node_value(
                runtime.content,
                node,
                "action",
            )
            if isinstance(action, str) and action:
                payload["action"] = action
            out.append(payload)
    return out


def location_items(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for item_id in items_at(runtime.graph_index, location_id):
        node = runtime.graph.nodes.get(item_id)
        if node is not None and node.type == "item":
            out.append(item_payload(runtime, node))
    return out


def attackable_ids(current_visible_targets: list[dict[str, Any]]) -> list[str]:
    return [
        target["id"]
        for target in current_visible_targets
        if target["type"] in {"npc", "enemy"} and target.get("protected") is not True
    ]


def merchants(
    runtime: GameRuntimeState,
    current_visible_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for target in current_visible_targets:
        node = runtime.graph.nodes.get(target["id"])
        if node is None or node.type != "character":
            continue
        if not isinstance(node.properties.get("gold"), int):
            continue
        stock = inventory_for_owner(runtime, node.id)
        if not stock:
            continue
        out.append({"id": node.id, "name": target["name"], "stock": stock})
    return out


def corpses(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for character_id in characters_at(runtime.graph_index, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or is_visible_character(node):
            continue
        current_inventory = inventory_for_owner(runtime, node.id)
        if current_inventory:
            out.append(
                {
                    "id": node.id,
                    "name": node_label(runtime.content, node),
                    "inventory": current_inventory,
                }
            )
    return out


def item_payload(runtime: GameRuntimeState, node: GraphNode) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": node.id,
        "name": node_label(runtime.content, node),
        "kind": item_kind(runtime, node),
    }
    price = node.properties.get("price")
    if isinstance(price, int):
        payload["price"] = price
    return payload


def node_ref(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, str] | None:
    if node is None:
        return None
    return {"id": node.id, "name": node_label(runtime.content, node)}


def item_kind(runtime: GameRuntimeState, node: GraphNode) -> str:
    value = node_value(runtime.content, node, "kind") or node_value(
        runtime.content,
        node,
        "type",
    )
    return value if isinstance(value, str) and value else "item"
