from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.content import node_value
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent
from src.game.runtime.state import GameRuntimeState


class StoryWriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: dict[str, Any]
    intent: dict[str, Any]
    player_input: str
    action: dict[str, Any]
    visible_context: dict[str, Any]


def build_story_write_input(
    runtime: GameRuntimeState,
    *,
    contract: StoryContract,
    intent: StoryWriteIntent,
    player_input: str,
    action: Action,
    accepted_narration: str | None = None,
    patch_required: bool = False,
    patch_reason: str | None = None,
) -> StoryWriteInput:
    visible_context: dict[str, Any] = {
        "player_id": runtime.progress.player_id,
        "turn": runtime.progress.turn_count,
        "nodes": _visible_nodes(runtime),
    }
    memories = _recent_memories(runtime)
    if memories:
        visible_context["memories"] = memories
    exchanges = _recent_exchanges(runtime)
    if exchanges:
        visible_context["recent_exchanges"] = exchanges
    if accepted_narration:
        visible_context["accepted_narration"] = accepted_narration
    if patch_required:
        visible_context["patch_requirement"] = {
            "required": True,
            "reason": patch_reason or "accepted narration contains an actionable lead",
        }
    return StoryWriteInput(
        contract=contract.model_dump(mode="json", by_alias=True),
        intent=intent.model_dump(mode="json"),
        player_input=player_input,
        action=action.model_dump(mode="json", by_alias=True, exclude_none=True),
        visible_context=visible_context,
    )


def _visible_nodes(runtime: GameRuntimeState) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for node in runtime.graph.nodes.values():
        if node.type not in {"character", "item", "location", "quest", "knowledge"}:
            continue
        payload: dict[str, Any] = {
            "id": node.id,
            "type": node.type,
            "name": node_value(runtime.content, node, "name")
            or node_value(runtime.content, node, "title")
            or node.id,
        }
        summary = node_value(runtime.content, node, "summary") or node_value(
            runtime.content,
            node,
            "description",
        )
        if isinstance(summary, str) and summary:
            payload["summary"] = summary
        if node.type == "knowledge":
            _copy_node_field(runtime, node, payload, "kind")
            _copy_node_field(runtime, node, payload, "visibility")
            _copy_node_field(runtime, node, payload, "anchor_id")
            _copy_node_field(runtime, node, payload, "turn_id")
        nodes.append(payload)
    return nodes


def _recent_memories(runtime: GameRuntimeState, *, limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "turn": memory.turn,
            "target": memory.target,
            "content": memory.content,
            "importance": memory.importance,
        }
        for memory in runtime.memories[-limit:]
    ]


def _recent_exchanges(runtime: GameRuntimeState, *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "turn": exchange.turn,
            "target": exchange.target,
            "player": exchange.player,
            "narrator": exchange.narrator,
        }
        for exchange in runtime.recent_exchanges[-limit:]
    ]


def _copy_node_field(
    runtime: GameRuntimeState,
    node,
    payload: dict[str, Any],
    key: str,
) -> None:
    value = node_value(runtime.content, node, key)
    if value is not None:
        payload[key] = value
