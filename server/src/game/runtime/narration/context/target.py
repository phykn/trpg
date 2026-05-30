from __future__ import annotations

import re
from typing import Any

from src.game.domain.content import node_label, node_text, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import inventory_of

from ...state import GameRuntimeState
from .base import item_payload, node_ref
from .knowledge import public_knowledge_payloads
from .style import (
    add_character_style_fields,
    dialogue_style_payload,
    faction_payload,
    mbti_payload,
)


def target_view(
    runtime: GameRuntimeState,
    node: GraphNode | None,
    *,
    player_input: str | None = None,
) -> dict[str, Any] | None:
    if node is None:
        return None
    payload = node_ref(runtime, node)
    payload["type"] = node.type
    role = node_value(runtime.content, node, "role")
    if isinstance(role, str) and role:
        payload["known_role"] = role
    tone_hint = node_text(runtime.content, node, "tone_hint")
    if tone_hint:
        payload["tone_hint"] = tone_hint
    add_character_style_fields(runtime, node, payload)
    faction = faction_payload(runtime, node)
    if faction:
        payload["faction"] = faction
    dialogue_style = dialogue_style_payload(runtime, node)
    if dialogue_style:
        payload["dialogue_style"] = dialogue_style
    mbti = mbti_payload(runtime, node)
    if mbti:
        payload["mbti"] = mbti
    public_knowledge = public_knowledge_payloads(runtime, node)
    if public_knowledge:
        payload["public_knowledge"] = public_knowledge
    available_items = mentioned_inventory_payloads(runtime, node, player_input)
    if available_items:
        payload["available_items"] = available_items
    return payload


def mentioned_inventory_payloads(
    runtime: GameRuntimeState,
    node: GraphNode,
    player_input: str | None,
) -> list[dict[str, Any]]:
    if node.type != "character" or not player_input:
        return []
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, node.id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        if not item_mentioned(player_input, node_label(runtime.content, item), item.id):
            continue
        payload: dict[str, Any] = item_payload(runtime, item)
        price = node_value(runtime.content, item, "price")
        if isinstance(price, int | float):
            payload["price"] = price
        out.append(payload)
    return out


def item_mentioned(player_input: str, item_name: str, item_id: str) -> bool:
    normalized_input = normalize_for_match(player_input)
    normalized_name = normalize_for_match(item_name)
    if normalized_name and normalized_name in normalized_input:
        return True
    normalized_id = normalize_for_match(item_id)
    if normalized_id and normalized_id in normalized_input:
        return True
    name_tokens = [
        normalize_for_match(token)
        for token in re.split(r"\s+", item_name)
        if len(normalize_for_match(token)) >= 2
    ]
    return sum(1 for token in name_tokens if token in normalized_input) >= 2


def normalize_for_match(text: str) -> str:
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return re.sub(rf"[^0-9A-Za-z{hangul_range}]+", "", text).lower()
