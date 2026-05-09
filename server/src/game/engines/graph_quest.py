from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
    RemoveEdgeChange,
    SetNodePropertyChange,
)
from src.game.domain.graph_query import edges_from, edges_to


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


class GraphQuestRewardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    quest_id: str
    player_id: str
    gold: int
    exp: int
    item_ids: list[str]


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


def plan_quest_rewards(
    graph: Graph,
    quest_id: str,
    player_id: str,
) -> GraphQuestRewardResult:
    quest = _require_quest(graph, quest_id)
    if _quest_status(quest) != "completed":
        raise GraphQuestError(f"quest rewards require completed status: {quest_id}")
    player = graph.nodes.get(player_id)
    if player is None:
        raise GraphQuestError(f"missing player: {player_id}")
    if player.type != "character":
        raise GraphQuestError(f"node is not a character: {player_id}")

    rewards = quest.properties.get("rewards", {})
    reward_data = rewards if isinstance(rewards, dict) else {}
    gold = _int_value(reward_data.get("gold"))
    exp = _int_value(reward_data.get("exp"))
    item_ids = _reward_item_ids(graph, quest_id, reward_data)

    changes: list[GraphChange] = []
    if gold:
        changes.append(_property_change(player_id, "gold", _int_value(player.properties.get("gold")) + gold))
    if exp:
        changes.append(_property_change(player_id, "xp_pool", _int_value(player.properties.get("xp_pool")) + exp))
    for item_id in item_ids:
        for edge in edges_to(graph, quest_id, "reward_of"):
            if edge.from_node_id == item_id:
                changes.append(RemoveEdgeChange(type="remove_edge", edge_id=edge.id))
        if not _has_carry_edge(graph, player_id, item_id):
            changes.append(
                AddEdgeChange(
                    type="add_edge",
                    edge=GraphEdge(
                        id=f"carries:{player_id}:{item_id}",
                        type="carries",
                        from_node_id=player_id,
                        to_node_id=item_id,
                    ),
                )
            )
    return GraphQuestRewardResult(
        changes=changes,
        quest_id=quest_id,
        player_id=player_id,
        gold=gold,
        exp=exp,
        item_ids=item_ids,
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


def _reward_item_ids(
    graph: Graph,
    quest_id: str,
    reward_data: dict[str, Any],
) -> list[str]:
    item_ids: list[str] = []
    raw_items = reward_data.get("items", [])
    if isinstance(raw_items, list):
        item_ids.extend(item for item in raw_items if isinstance(item, str))
    item_ids.extend(edge.from_node_id for edge in edges_to(graph, quest_id, "reward_of"))
    return sorted(set(item_ids))


def _has_carry_edge(graph: Graph, player_id: str, item_id: str) -> bool:
    return any(edge.to_node_id == item_id for edge in edges_from(graph, player_id, "carries"))


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


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
