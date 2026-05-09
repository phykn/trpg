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


class GraphQuestProgressResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    completed_quest_ids: list[str]


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


def plan_quest_progress_for_character_defeat(
    graph: Graph,
    character_id: str,
) -> GraphQuestProgressResult:
    changes: list[GraphChange] = []
    completed_quest_ids: list[str] = []
    for quest in graph.nodes.values():
        if quest.type != "quest" or _quest_status(quest) != "active":
            continue
        triggers = _quest_triggers(quest)
        triggers_met = _quest_triggers_met(quest, len(triggers))
        changed = False
        for index, trigger in enumerate(triggers):
            if triggers_met[index]:
                continue
            if (
                trigger.get("type") in {"character_defeat", "character_death"}
                and trigger.get("target_id") == character_id
            ):
                triggers_met[index] = True
                changed = True
        if not changed:
            continue
        changes.append(_property_change(quest.id, "triggers_met", triggers_met))
        if triggers and all(triggers_met):
            changes.append(_status_change(quest.id, "completed"))
            completed_quest_ids.append(quest.id)
    return GraphQuestProgressResult(
        changes=changes,
        completed_quest_ids=completed_quest_ids,
    )


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


def _quest_triggers(quest: GraphNode) -> list[dict[str, Any]]:
    triggers = quest.properties.get("triggers", [])
    if not isinstance(triggers, list):
        return []
    return [trigger for trigger in triggers if isinstance(trigger, dict)]


def _quest_triggers_met(quest: GraphNode, total: int) -> list[bool]:
    raw = quest.properties.get("triggers_met", [])
    values = raw if isinstance(raw, list) else []
    padded = [*values[:total], *([False] * max(0, total - len(values)))]
    return [item if isinstance(item, bool) else False for item in padded]


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
    value: Any,
) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=quest_id,
        path=path,
        value=value,
    )
