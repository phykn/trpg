from __future__ import annotations

from typing import Any

from src.game.domain.content import node_text, node_value
from src.game.domain.graph import GraphNode

from ...state import GameRuntimeState


def string_list_value(
    runtime: GameRuntimeState,
    node: GraphNode,
    key: str,
) -> list[str]:
    value = node_value(runtime.content, node, key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def add_text_field(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
    key: str,
) -> None:
    value = node_text(runtime.content, node, key)
    if value:
        payload[key] = value


def add_list_field(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
    key: str,
) -> None:
    values = string_list_value(runtime, node, key)
    if values:
        payload[key] = values
