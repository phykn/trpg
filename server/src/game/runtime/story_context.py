from typing import Any

from src.game.domain.content import node_label, node_text
from src.game.domain.graph import GraphNode

from .state import GameRuntimeState


def current_story_payload(
    runtime: GameRuntimeState,
    *,
    include_status: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    chapter = _active_chapter(runtime, include_status=include_status)
    if chapter is not None:
        payload["chapter"] = chapter
    quest = _active_quest(runtime, include_status=include_status)
    if quest is not None:
        payload["active_quest"] = quest
    return payload


def _active_chapter(
    runtime: GameRuntimeState,
    *,
    include_status: bool,
) -> dict[str, Any] | None:
    for node in runtime.graph.nodes.values():
        if node.type == "chapter" and node.properties.get("status") == "active":
            return _story_node_payload(runtime, node, include_status=include_status)
    return None


def _active_quest(
    runtime: GameRuntimeState,
    *,
    include_status: bool,
) -> dict[str, Any] | None:
    quest_id = runtime.progress.active_quest_id
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return None
    return _story_node_payload(runtime, node, include_status=include_status)


def _story_node_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
    *,
    include_status: bool,
) -> dict[str, Any]:
    payload = {"id": node.id, "name": node_label(runtime.content, node)}
    status = node.properties.get("status")
    if include_status and isinstance(status, str) and status:
        payload["status"] = status
    description = node_text(runtime.content, node, "description") or node_text(
        runtime.content,
        node,
        "summary",
    )
    if description:
        payload["description"] = description
    guidance = node.properties.get("guidance")
    if isinstance(guidance, str) and guidance.strip():
        payload["guidance"] = guidance.strip()
    elif isinstance(guidance, list):
        items = [
            item.strip()
            for item in guidance
            if isinstance(item, str) and item.strip()
        ]
        if items:
            payload["guidance"] = items
    return payload
