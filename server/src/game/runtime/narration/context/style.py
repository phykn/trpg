from __future__ import annotations

from typing import Any

from src.game.domain.content import node_label, node_text
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import edges_from

from ...state import GameRuntimeState
from .fields import add_list_field, add_text_field


def add_character_style_fields(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
) -> None:
    for key in ("personality", "traits"):
        add_list_field(runtime, node, payload, key)
    for key in (
        "background",
        "appearance",
        "desire",
        "fear",
        "contradiction",
        "personal_boundary",
    ):
        add_text_field(runtime, node, payload, key)


def faction_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "member_of_faction"):
        faction = runtime.graph.nodes.get(edge.to_node_id)
        if faction is None or faction.type != "faction":
            continue
        payload: dict[str, Any] = {
            "id": faction.id,
            "name": node_label(runtime.content, faction),
        }
        description = node_text(runtime.content, faction, "description")
        if description:
            payload["description"] = description
        add_list_field(runtime, faction, payload, "traits")
        return payload
    return None


def dialogue_style_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "uses_dialogue_style"):
        style = runtime.graph.nodes.get(edge.to_node_id)
        if style is None or style.type != "dialogue_style":
            continue
        payload: dict[str, Any] = {
            "id": style.id,
            "name": node_label(runtime.content, style),
        }
        for key in ("speech_style", "humor_style"):
            add_text_field(runtime, style, payload, key)
        add_list_field(runtime, style, payload, "traits")
        return payload
    return None


def mbti_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "has_mbti"):
        mbti = runtime.graph.nodes.get(edge.to_node_id)
        if mbti is None or mbti.type != "mbti":
            continue
        payload: dict[str, Any] = {}
        for key in (
            "attitude",
            "speech_style",
            "boundary_style",
            "humor_style",
        ):
            add_text_field(runtime, mbti, payload, key)
        for key in ("roleplay_cues", "avoid"):
            add_list_field(runtime, mbti, payload, key)
        return payload
    return None
