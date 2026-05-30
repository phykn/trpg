from __future__ import annotations

from typing import Any

from src.game.runtime.state import GameRuntimeState

from .entities import node_ref
from .types import ClassifyContextLimits


def last_entity_ref(
    runtime: GameRuntimeState,
    *,
    entity_types: set[str] | None = None,
) -> dict[str, str] | None:
    subject_id = runtime.progress.active_subject_id
    node = runtime.graph.nodes.get(subject_id or "")
    if node is None:
        return None
    if entity_types is not None and node.type not in entity_types:
        return None
    return node_ref(runtime, node)


def recent_exchanges(
    runtime: GameRuntimeState,
    limits: ClassifyContextLimits,
) -> list[dict[str, Any]]:
    """Recent raw player input + narrator reply pairs, not free-form NPC memory."""
    return [
        {"turn": pair.turn, "player": pair.player, "narrator": pair.narrator}
        for pair in runtime.recent_exchanges[-limits.recent_exchanges :]
    ]


def recent_scene(
    runtime: GameRuntimeState,
    limits: ClassifyContextLimits,
) -> list[dict[str, Any]]:
    recent_exchange_turns = {
        pair.turn for pair in runtime.recent_exchanges[-limits.recent_exchanges :]
    }
    return [
        {
            "turn": entry.turn,
            "summary": entry.summary,
            **({"target": entry.target} if entry.target else {}),
        }
        for entry in [
            entry
            for entry in runtime.turn_log
            if entry.turn not in recent_exchange_turns
        ][-limits.recent_scene :]
        if entry.summary
    ]
