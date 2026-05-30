from __future__ import annotations

from typing import Any

from src.game.domain.content import node_label
from src.game.domain.graph.character import graph_character_kind, is_visible_character
from src.game.domain.graph.query import characters_at, edges_from, items_at, location_of

from ...state import GameRuntimeState
from .base import item_payload, node_ref
from .style import add_character_style_fields, dialogue_style_payload, mbti_payload


def scene_anchor(runtime: GameRuntimeState) -> dict[str, Any]:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    place_id = location_of(graph, player_id)
    place = runtime.graph.nodes.get(place_id or "")
    visible_names = [
        entry["name"]
        for entry in [
            *visible_character_payloads(runtime, place_id, exclude_id=player_id),
            *visible_item_payloads(runtime, place_id),
            *exit_payloads(runtime, place_id),
        ][:5]
    ]
    return {
        "location": node_ref(runtime, place),
        "visible_names": visible_names,
    }


def visible_character_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
    *,
    exclude_id: str,
) -> list[dict[str, Any]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for character_id in characters_at(runtime.graph_index, place_id):
        if character_id == exclude_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        payload: dict[str, Any] = {
            "id": node.id,
            "name": node_label(runtime.content, node),
            "type": graph_character_kind(node),
        }
        add_character_style_fields(runtime, node, payload)
        dialogue_style = dialogue_style_payload(runtime, node)
        if dialogue_style:
            payload["dialogue_style"] = dialogue_style
        mbti = mbti_payload(runtime, node)
        if mbti:
            payload["mbti"] = mbti
        out.append(payload)
    return out


def visible_item_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, Any]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for item_id in items_at(runtime.graph_index, place_id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        out.append(item_payload(runtime, item))
    return out


def exit_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, str]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, place_id, "connects_to"):
        target = runtime.graph.nodes.get(edge.to_node_id)
        if target is not None and target.type == "location":
            out.append({"id": target.id, "name": node_label(runtime.content, target)})
    return out
