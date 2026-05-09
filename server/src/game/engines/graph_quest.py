from __future__ import annotations

from typing import Literal

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

_TERMINAL_STATUSES: frozenset[str] = frozenset(
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


def plan_quest_accept(graph: Graph, quest_id: str) -> GraphQuestResult:
    quest = _require_quest(graph, quest_id)
    status = _quest_status(quest)
    if status in _TERMINAL_STATUSES:
        raise GraphQuestError(f"terminal quest cannot change state: {quest_id}")
    if status == "active":
        return _result(quest_id, "accept", status, "active", [])
    if status not in {"locked", "pending"}:
        raise GraphQuestError(f"quest cannot be accepted from {status}: {quest_id}")
    return _status_result(quest_id, "accept", status, "active")


def plan_quest_abandon(graph: Graph, quest_id: str) -> GraphQuestResult:
    quest = _require_quest(graph, quest_id)
    status = _quest_status(quest)
    _reject_terminal(status, quest_id)
    if status not in {"pending", "active"}:
        raise GraphQuestError(f"quest cannot be abandoned from {status}: {quest_id}")
    return _status_result(quest_id, "abandon", status, "abandoned")


def plan_quest_complete(
    graph: Graph,
    quest_id: str,
    *,
    reason: str | None = None,
) -> GraphQuestResult:
    quest = _require_quest(graph, quest_id)
    status = _quest_status(quest)
    _reject_terminal(status, quest_id)
    if status != "active":
        raise GraphQuestError(f"quest cannot be completed from {status}: {quest_id}")
    changes = [_status_change(quest_id, "completed")]
    if reason:
        changes.append(_property_change(quest_id, "success_reason", reason))
    return _result(quest_id, "complete", status, "completed", changes)


def plan_quest_fail(
    graph: Graph,
    quest_id: str,
    *,
    reason: str | None = None,
) -> GraphQuestResult:
    quest = _require_quest(graph, quest_id)
    status = _quest_status(quest)
    _reject_terminal(status, quest_id)
    if status not in {"pending", "active"}:
        raise GraphQuestError(f"quest cannot fail from {status}: {quest_id}")
    changes = [_status_change(quest_id, "failed")]
    if reason:
        changes.append(_property_change(quest_id, "fail_reason", reason))
    return _result(quest_id, "fail", status, "failed", changes)


def _require_quest(graph: Graph, quest_id: str) -> GraphNode:
    node = graph.nodes.get(quest_id)
    if node is None:
        raise GraphQuestError(f"missing quest: {quest_id}")
    if node.type != "quest":
        raise GraphQuestError(f"node is not a quest: {quest_id}")
    return node


def _quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    if not isinstance(status, str):
        raise GraphQuestError(f"missing quest status: {quest.id}")
    return status


def _reject_terminal(status: str, quest_id: str) -> None:
    if status in _TERMINAL_STATUSES:
        raise GraphQuestError(f"terminal quest cannot change state: {quest_id}")


def _status_result(
    quest_id: str,
    action: QuestAction,
    previous_status: str,
    next_status: QuestStatus,
) -> GraphQuestResult:
    return _result(
        quest_id,
        action,
        previous_status,
        next_status,
        [_status_change(quest_id, next_status)],
    )


def _result(
    quest_id: str,
    action: QuestAction,
    previous_status: str,
    next_status: str,
    changes: list[GraphChange],
) -> GraphQuestResult:
    return GraphQuestResult(
        changes=changes,
        quest_id=quest_id,
        action=action,
        previous_status=previous_status,
        next_status=next_status,
    )


def _status_change(quest_id: str, status: QuestStatus) -> SetNodePropertyChange:
    return _property_change(quest_id, "status", status)


def _property_change(
    quest_id: str,
    path: str,
    value: str,
) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=quest_id,
        path=path,
        value=value,
    )
