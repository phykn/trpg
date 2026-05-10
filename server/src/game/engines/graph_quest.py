from __future__ import annotations

from src.game.domain.graph import Graph, GraphChange
from src.game.engines.graph_quest_common import (
    TERMINAL_STATUSES,
    GraphQuestError,
    GraphQuestProgressResult,
    GraphQuestResult,
    GraphQuestRewardResult,
    QuestAction,
    QuestStatus,
    property_change,
    quest_status,
    reject_terminal,
    require_quest,
    status_change,
)
from src.game.engines.graph_quest_progress import (
    plan_quest_progress_for_character_defeat,
)
from src.game.engines.graph_quest_rewards import plan_quest_rewards

__all__ = [
    "GraphQuestError",
    "GraphQuestProgressResult",
    "GraphQuestResult",
    "GraphQuestRewardResult",
    "plan_quest_abandon",
    "plan_quest_accept",
    "plan_quest_complete",
    "plan_quest_fail",
    "plan_quest_progress_for_character_defeat",
    "plan_quest_rewards",
]


def plan_quest_accept(graph: Graph, quest_id: str) -> GraphQuestResult:
    quest = require_quest(graph, quest_id)
    status = quest_status(quest)
    if status in TERMINAL_STATUSES:
        raise GraphQuestError(f"terminal quest cannot change state: {quest_id}")
    if status == "active":
        return _result(quest_id, "accept", status, "active", [])
    if status not in {"locked", "pending"}:
        raise GraphQuestError(f"quest cannot be accepted from {status}: {quest_id}")
    return _status_result(quest_id, "accept", status, "active")


def plan_quest_abandon(graph: Graph, quest_id: str) -> GraphQuestResult:
    quest = require_quest(graph, quest_id)
    status = quest_status(quest)
    reject_terminal(status, quest_id)
    if status not in {"pending", "active"}:
        raise GraphQuestError(f"quest cannot be abandoned from {status}: {quest_id}")
    return _status_result(quest_id, "abandon", status, "abandoned")


def plan_quest_complete(
    graph: Graph,
    quest_id: str,
    *,
    reason: str | None = None,
) -> GraphQuestResult:
    quest = require_quest(graph, quest_id)
    status = quest_status(quest)
    reject_terminal(status, quest_id)
    if status != "active":
        raise GraphQuestError(f"quest cannot be completed from {status}: {quest_id}")
    changes = [status_change(quest_id, "completed")]
    if reason:
        changes.append(property_change(quest_id, "success_reason", reason))
    return _result(quest_id, "complete", status, "completed", changes)


def plan_quest_fail(
    graph: Graph,
    quest_id: str,
    *,
    reason: str | None = None,
) -> GraphQuestResult:
    quest = require_quest(graph, quest_id)
    status = quest_status(quest)
    reject_terminal(status, quest_id)
    if status not in {"pending", "active"}:
        raise GraphQuestError(f"quest cannot fail from {status}: {quest_id}")
    changes = [status_change(quest_id, "failed")]
    if reason:
        changes.append(property_change(quest_id, "fail_reason", reason))
    return _result(quest_id, "fail", status, "failed", changes)


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
        [status_change(quest_id, next_status)],
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
