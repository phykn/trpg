from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import Graph, GraphChange, GraphNode, SetNodePropertyChange


QuestStatus = Literal[
    "locked",
    "pending",
    "active",
    "completed",
    "failed",
    "abandoned",
]
QuestAction = Literal["accept", "abandon", "complete", "fail"]

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "abandoned"}
)


class GraphQuestError(ValueError):
    pass


class GraphQuestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    quest_id: str
    action: QuestAction
    previous_status: str
    next_status: str


class GraphQuestProgressResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    completed_quest_ids: list[str]


class GraphQuestRewardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    quest_id: str
    player_id: str
    gold: int
    exp: int
    item_ids: list[str]


def require_quest(graph: Graph, quest_id: str) -> GraphNode:
    node = graph.nodes.get(quest_id)
    if node is None:
        raise GraphQuestError(f"missing quest: {quest_id}")
    if node.type != "quest":
        raise GraphQuestError(f"node is not a quest: {quest_id}")
    return node


def quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    if not isinstance(status, str):
        raise GraphQuestError(f"missing quest status: {quest.id}")
    return status


def reject_terminal(status: str, quest_id: str) -> None:
    if status in TERMINAL_STATUSES:
        raise GraphQuestError(f"terminal quest cannot change state: {quest_id}")


def status_change(quest_id: str, status: QuestStatus) -> SetNodePropertyChange:
    return property_change(quest_id, "status", status)


def property_change(
    quest_id: str,
    path: str,
    value: Any,
) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=quest_id,
        path=path,
        value=value,
    )


def int_value(value: object) -> int:
    return value if isinstance(value, int) else 0
