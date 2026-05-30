from __future__ import annotations

from typing import Any

from src.game.domain.content import node_label, node_text, node_value
from src.game.domain.graph import GraphNode
from src.locale.render import render

from ...state import GameRuntimeState
from .fields import add_list_field, add_text_field


def place_payload(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, Any] | None:
    if node is None or node.type != "location":
        return None
    payload = {"id": node.id, "name": node_label(runtime.content, node)}
    description = node_text(runtime.content, node, "description")
    if description:
        payload["description"] = description
    add_text_field(runtime, node, payload, "mood")
    add_list_field(runtime, node, payload, "traits")
    return payload


def world_guidance(runtime: GameRuntimeState) -> str | None:
    text = runtime.content.world_guidance.strip()
    if not text:
        return None
    return text


def item_payload(runtime: GameRuntimeState, item: GraphNode) -> dict[str, Any]:
    kind = node_value(runtime.content, item, "kind") or node_value(
        runtime.content,
        item,
        "type",
    )
    payload: dict[str, Any] = {
        "id": item.id,
        "name": node_label(runtime.content, item),
        "kind": kind if isinstance(kind, str) and kind else "item",
    }
    description = node_text(runtime.content, item, "description")
    if description:
        payload["description"] = description
    add_list_field(runtime, item, payload, "traits")
    return payload


def node_ref(runtime: GameRuntimeState, node: GraphNode | None) -> dict[str, str]:
    if node is None:
        return {"id": "", "name": render("runtime.none", runtime.progress.locale)}
    return {"id": node.id, "name": node_label(runtime.content, node)}
