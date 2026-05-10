from __future__ import annotations

from typing import Literal

from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_character import is_visible_character
from src.game.domain.graph_query import (
    characters_at,
    edges_to,
    location_of,
    nodes_of_type,
)
from src.game.runtime.state import GameRuntimeState
from src.wire.graph_payload_helpers import node_name, optional_str
from src.wire.labels import difficulty_badge
from src.wire.models import DifficultyBadge, QuestPayload, QuestRewards


def active_quest_payload(runtime: GameRuntimeState) -> QuestPayload | None:
    graph = runtime.graph
    active_quest_id = runtime.progress.active_quest_id
    if active_quest_id is not None:
        quest = graph.nodes.get(active_quest_id)
        if (
            quest is not None
            and quest.type == "quest"
            and quest_status(quest) == "active"
        ):
            return build_quest_payload(graph, quest)

    active = _first_quest_with_status(graph, "active")
    if active is not None:
        return build_quest_payload(graph, active)
    return None


def quest_offer_payloads(runtime: GameRuntimeState) -> list[QuestPayload]:
    graph = runtime.graph
    location_id = location_of(graph, runtime.progress.player_id)
    if location_id is None:
        return []
    visible_characters = set(characters_at(graph, location_id))
    offers: list[QuestPayload] = []
    for edge in graph.edges.values():
        if edge.type != "gives_quest" or edge.from_node_id not in visible_characters:
            continue
        giver = graph.nodes.get(edge.from_node_id)
        if giver is None or not is_visible_character(giver):
            continue
        quest = graph.nodes.get(edge.to_node_id)
        if quest is None or quest.type != "quest":
            continue
        if quest_status(quest) in {"locked", "pending"}:
            offers.append(build_quest_payload(graph, quest))
    return offers


def build_quest_payload(graph: Graph, quest: GraphNode) -> QuestPayload:
    status = quest_status(quest)
    display_status = (
        status
        if status in {"pending", "active", "completed", "failed"}
        else "pending"
    )
    actions: list[Literal["accept", "abandon"]] = []
    if status in {"locked", "pending"}:
        actions.append("accept")
    elif status == "active":
        actions.append("abandon")

    tier = optional_str(quest.properties.get("difficulty")) or "normal"
    badge = difficulty_badge(tier)
    goals = _quest_goals(quest)
    done, total = _quest_progress(quest)
    return QuestPayload(
        id=quest.id,
        title=optional_str(quest.properties.get("title")) or quest.id,
        summary=optional_str(quest.properties.get("summary")) or "",
        giver=_quest_giver_name(graph, quest.id),
        difficulty=DifficultyBadge(label=badge["label"], tone=badge["tone"]),
        goals=goals,
        progress_label=_progress_label(done, total),
        rewards=_quest_rewards(quest),
        status=display_status,
        actions=actions,
    )


def quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    return status if isinstance(status, str) else "locked"


def _first_quest_with_status(graph: Graph, status: str) -> GraphNode | None:
    for quest in nodes_of_type(graph, "quest"):
        if quest_status(quest) == status:
            return quest
    return None


def _quest_goals(quest: GraphNode) -> list[str]:
    raw = quest.properties.get("triggers", [])
    if not isinstance(raw, list):
        return []
    goals: list[str] = []
    for trigger in raw:
        if not isinstance(trigger, dict):
            continue
        name = trigger.get("name")
        if isinstance(name, str) and name:
            goals.append(name)
    return goals


def _quest_progress(quest: GraphNode) -> tuple[int, int]:
    raw_goals = quest.properties.get("triggers", [])
    raw_met = quest.properties.get("triggers_met", [])
    total = len(raw_goals) if isinstance(raw_goals, list) else 0
    if not isinstance(raw_met, list):
        return 0, total
    return sum(1 for item in raw_met[:total] if item is True), total


def _progress_label(done: int, total: int) -> str:
    if total == 0:
        return ""
    if done >= total:
        return "✓"
    return f"{done}/{total}"


def _quest_rewards(quest: GraphNode) -> QuestRewards:
    raw = quest.properties.get("rewards", {})
    if not isinstance(raw, dict):
        return QuestRewards(gold=0, exp=0)
    gold = raw.get("gold")
    exp = raw.get("exp")
    return QuestRewards(
        gold=gold if isinstance(gold, int) else 0,
        exp=exp if isinstance(exp, int) else 0,
    )


def _quest_giver_name(graph: Graph, quest_id: str) -> str:
    for edge in edges_to(graph, quest_id, "gives_quest"):
        giver = graph.nodes.get(edge.from_node_id)
        if giver is not None:
            return node_name(giver)
    return ""
