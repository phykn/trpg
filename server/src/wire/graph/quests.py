from collections import deque
from typing import Literal

from src.game.domain.content import RuntimeContent, node_record
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph.character import is_visible_character
from src.game.domain.graph.query import (
    characters_at,
    edges_to,
    location_of,
    nodes_of_type,
)
from src.game.runtime.state import GameRuntimeState
from src.locale import render
from src.wire.models import DifficultyBadge, QuestPayload, QuestRewards

from .values import node_name, optional_str, static_value


def active_quest_payload(runtime: GameRuntimeState) -> QuestPayload | None:
    graph = runtime.graph_index
    active_quest_id = runtime.progress.active_quest_id
    if active_quest_id is not None:
        quest = graph.nodes.get(active_quest_id)
        if (
            quest is not None
            and quest.type == "quest"
            and quest_status(quest) == "active"
        ):
            return build_quest_payload(graph, quest, runtime)

    active = _first_quest_with_status(graph, "active")
    if active is not None:
        return build_quest_payload(graph, active, runtime)
    return None


def quest_offer_payloads(runtime: GameRuntimeState) -> list[QuestPayload]:
    graph = runtime.graph_index
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
            offers.append(build_quest_payload(graph, quest, runtime))
    return offers


def build_quest_payload(
    graph: Graph,
    quest: GraphNode,
    runtime: GameRuntimeState,
) -> QuestPayload:
    status = quest_status(quest)
    display_status = (
        status if status in {"pending", "active", "completed", "failed"} else "pending"
    )
    actions: list[Literal["accept", "abandon"]] = []
    if status in {"locked", "pending"}:
        actions.append("accept")
    elif status == "active":
        actions.append("abandon")

    content = runtime.content
    tier = optional_str(static_value(quest, "difficulty", content)) or "normal"
    goals = _quest_goals(quest, runtime)
    done, total = _quest_progress(quest)
    return QuestPayload(
        id=quest.id,
        title=optional_str(static_value(quest, "title", content)) or quest.id,
        summary=optional_str(static_value(quest, "summary", content)) or "",
        giver=_quest_giver_name(graph, quest.id, runtime),
        difficulty=_difficulty_badge(tier),
        goals=goals,
        progress_label=_progress_label(done, total),
        rewards=_quest_rewards(quest),
        status=display_status,
        actions=actions,
    )


def quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    return status if isinstance(status, str) else "locked"


def _difficulty_badge(tier: str) -> DifficultyBadge:
    return DifficultyBadge(label=render(f"tier.{tier}", "ko"))


def _first_quest_with_status(graph: Graph, status: str) -> GraphNode | None:
    for quest in nodes_of_type(graph, "quest"):
        if quest_status(quest) == status:
            return quest
    return None


def _quest_goals(quest: GraphNode, runtime: GameRuntimeState) -> list[str]:
    raw = quest.properties.get("triggers", [])
    if not isinstance(raw, list):
        return []
    content = runtime.content
    content_names = _trigger_names_by_id(content, quest)
    goals: list[str] = []
    for trigger in raw:
        if not isinstance(trigger, dict):
            continue
        routed_goal = _route_goal_for_location_trigger(trigger, runtime)
        if routed_goal is not None:
            goals.append(routed_goal)
            continue
        name = trigger.get("name")
        if name is None:
            trigger_id = trigger.get("id")
            name = (
                content_names.get(trigger_id) if isinstance(trigger_id, str) else None
            )
        if isinstance(name, str) and name:
            if _should_mark_social_goal_retry(trigger, quest, runtime):
                name = render("ui.quest.goal_retry", "ko", goal=name)
            goals.append(name)
    return goals


def _route_goal_for_location_trigger(
    trigger: dict,
    runtime: GameRuntimeState,
) -> str | None:
    if trigger.get("type") != "location_enter":
        return None
    target_id = trigger.get("target")
    if not isinstance(target_id, str):
        return None
    graph = runtime.graph_index
    current_id = location_of(graph, runtime.progress.player_id)
    if current_id is None or current_id == target_id:
        return None
    next_step_id = _first_step_toward_location(graph, current_id, target_id)
    if next_step_id is None or next_step_id == target_id:
        return None
    next_step = graph.nodes.get(next_step_id)
    target = graph.nodes.get(target_id)
    if next_step is None or target is None:
        return None
    return render(
        "ui.quest.goal_via",
        "ko",
        via=node_name(next_step, runtime.content),
        target=node_name(target, runtime.content),
    )


def _should_mark_social_goal_retry(
    trigger: dict,
    quest: GraphNode,
    runtime: GameRuntimeState,
) -> bool:
    if trigger.get("type") != "social_check":
        return False
    if not _latest_roll_failed(runtime):
        return False
    raw_triggers = quest.properties.get("triggers", [])
    raw_met = quest.properties.get("triggers_met", [])
    if not isinstance(raw_triggers, list) or not isinstance(raw_met, list):
        return True
    for index, candidate in enumerate(raw_triggers):
        if candidate is trigger:
            return index >= len(raw_met) or raw_met[index] is not True
    return True


def _latest_roll_failed(runtime: GameRuntimeState) -> bool:
    for entry in reversed(runtime.log_entries):
        kind = getattr(entry, "kind", None)
        if kind == "gm":
            continue
        if kind == "roll":
            return getattr(entry, "result", None) == "fail"
        return False
    return False


def _first_step_toward_location(
    graph: Graph,
    current_id: str,
    target_id: str,
) -> str | None:
    queue = deque([(current_id, None)])
    visited = {current_id}
    while queue:
        location_id, first_step = queue.popleft()
        for edge in graph.edges.values():
            if edge.type != "connects_to" or edge.from_node_id != location_id:
                continue
            if edge.to_node_id in visited:
                continue
            step = first_step or edge.to_node_id
            if edge.to_node_id == target_id:
                return step
            visited.add(edge.to_node_id)
            queue.append((edge.to_node_id, step))
    return None


def _trigger_names_by_id(content: RuntimeContent, quest: GraphNode) -> dict[str, str]:
    raw = node_record(content, quest).get("triggers", [])
    if not isinstance(raw, list):
        return {}
    names: dict[str, str] = {}
    for trigger in raw:
        if not isinstance(trigger, dict):
            continue
        trigger_id = trigger.get("id")
        name = trigger.get("name")
        if isinstance(trigger_id, str) and isinstance(name, str) and name:
            names[trigger_id] = name
    return names


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


def _quest_giver_name(graph: Graph, quest_id: str, runtime: GameRuntimeState) -> str:
    for edge in edges_to(graph, quest_id, "gives_quest"):
        giver = graph.nodes.get(edge.from_node_id)
        if giver is not None:
            return node_name(giver, runtime.content)
    return ""
