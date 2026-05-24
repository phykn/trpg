from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.graph import Graph, SetNodePropertyChange
from src.game.domain.quest import quest_choices, quest_triggers, quest_triggers_met


class GraphProgressionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[SetNodePropertyChange]
    next_active_quest_id: str | None
    completed_chapter_ids: list[str]
    auto_completed_quest_ids: list[str] = Field(default_factory=list)
    scenario_completed: bool = False


def plan_progression_after_quest_completion(
    graph: Graph,
    *,
    completed_quest_ids: list[str],
    active_quest_id: str | None,
    satisfied_location_ids: set[str] | None = None,
) -> GraphProgressionResult:
    statuses = {
        node_id: _node_status(node)
        for node_id, node in graph.nodes.items()
        if node.type in {"quest", "chapter"}
    }
    changes: list[SetNodePropertyChange] = []
    completed_chapter_ids: list[str] = []
    auto_completed_quest_ids: list[str] = []
    completed = set(completed_quest_ids)
    next_active_quest_id = None if active_quest_id in completed else active_quest_id
    satisfied_locations = satisfied_location_ids or set()

    def status(node_id: str) -> str:
        return statuses.get(node_id, "locked")

    def set_status(node_id: str, value: str) -> None:
        if status(node_id) == value:
            return
        statuses[node_id] = value
        changes.append(
            SetNodePropertyChange(
                type="set_node_property",
                node_id=node_id,
                path="status",
                value=value,
            )
        )

    while True:
        changed = False

        for chapter_id in _chapter_ids(graph):
            quest_ids = _quest_ids_for_chapter(graph, chapter_id)
            required_ids = [
                quest_id
                for quest_id in quest_ids
                if _is_required_quest(graph, quest_id)
            ]
            if required_ids and all(status(quest_id) == "completed" for quest_id in required_ids):
                if status(chapter_id) != "completed":
                    set_status(chapter_id, "completed")
                    completed_chapter_ids.append(chapter_id)
                    changed = True

        for chapter_id in _chapter_ids(graph):
            if status(chapter_id) == "locked" and _prerequisites_met(graph, chapter_id, status):
                set_status(chapter_id, "active")
                changed = True

        for quest_id in _quest_ids(graph):
            if status(quest_id) != "locked":
                continue
            if not _prerequisite_ids(graph, quest_id):
                continue
            if not _prerequisites_met(graph, quest_id, status):
                continue
            if _auto_activate_when_unlocked(graph, quest_id) and next_active_quest_id is None:
                set_status(quest_id, "active")
                next_active_quest_id = quest_id
            else:
                set_status(quest_id, "pending")
            changed = True

        auto_completed = _auto_complete_satisfied_location_quest(
            graph,
            status,
            next_active_quest_id,
            satisfied_locations,
            changes,
        )
        if auto_completed is not None:
            set_status(auto_completed, "completed")
            auto_completed_quest_ids.append(auto_completed)
            next_active_quest_id = None
            changed = True

        if not changed:
            break

    required_quest_ids = [
        quest_id for quest_id in _quest_ids(graph) if _is_required_quest(graph, quest_id)
    ]
    scenario_completed = bool(required_quest_ids) and all(
        status(quest_id) == "completed" for quest_id in required_quest_ids
    )

    return GraphProgressionResult(
        changes=changes,
        next_active_quest_id=next_active_quest_id,
        auto_completed_quest_ids=auto_completed_quest_ids,
        completed_chapter_ids=completed_chapter_ids,
        scenario_completed=scenario_completed,
    )


def _node_status(node) -> str:
    status = node.properties.get("status")
    return status if isinstance(status, str) else "locked"


def _chapter_ids(graph: Graph) -> list[str]:
    return [node.id for node in graph.nodes.values() if node.type == "chapter"]


def _quest_ids(graph: Graph) -> list[str]:
    return [node.id for node in graph.nodes.values() if node.type == "quest"]


def _quest_ids_for_chapter(graph: Graph, chapter_id: str) -> list[str]:
    ids = [
        edge.from_node_id
        for edge in graph.edges.values()
        if edge.type == "part_of_chapter" and edge.to_node_id == chapter_id
    ]
    node = graph.nodes[chapter_id]
    raw = node.properties.get("quests")
    if isinstance(raw, list):
        ids.extend(item for item in raw if isinstance(item, str))
    return list(dict.fromkeys(ids))


def _is_required_quest(graph: Graph, quest_id: str) -> bool:
    node = graph.nodes.get(quest_id)
    return node is not None and node.type == "quest" and node.properties.get("required") is not False


def _auto_activate_when_unlocked(graph: Graph, quest_id: str) -> bool:
    node = graph.nodes.get(quest_id)
    return (
        node is not None
        and node.type == "quest"
        and node.properties.get("auto_activate_when_unlocked") is True
    )


def _prerequisites_met(graph: Graph, node_id: str, status) -> bool:
    return all(status(prereq_id) == "completed" for prereq_id in _prerequisite_ids(graph, node_id))


def _prerequisite_ids(graph: Graph, node_id: str) -> list[str]:
    node = graph.nodes[node_id]
    raw = node.properties.get("prerequisites", [])
    return [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []

def _auto_complete_satisfied_location_quest(
    graph: Graph,
    status,
    quest_id: str | None,
    satisfied_location_ids: set[str],
    changes: list[SetNodePropertyChange],
) -> str | None:
    quest_id = _auto_completable_location_quest_id(
        graph,
        status,
        quest_id,
        satisfied_location_ids,
    )
    if quest_id is None:
        return None
    quest = graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None
    triggers = quest_triggers(quest)
    if not triggers:
        return None
    triggers_met = quest_triggers_met(quest, len(triggers))
    changed = False
    for index, trigger in enumerate(triggers):
        if triggers_met[index]:
            continue
        if trigger.get("type") == "location_enter" and trigger.get("target") in satisfied_location_ids:
            triggers_met[index] = True
            changed = True
    if not changed:
        return None
    changes.append(
        SetNodePropertyChange(
            type="set_node_property",
            node_id=quest_id,
            path="triggers_met",
            value=triggers_met,
        )
    )
    if all(triggers_met) and not quest_choices(quest):
        return quest_id
    return None


def _auto_completable_location_quest_id(
    graph: Graph,
    status,
    active_quest_id: str | None,
    satisfied_location_ids: set[str],
) -> str | None:
    if active_quest_id is None or status(active_quest_id) != "active":
        return None
    quest = graph.nodes.get(active_quest_id)
    if quest is None or quest.type != "quest":
        return None
    if quest.properties.get("auto_complete_when_satisfied") is not True:
        return None
    if _location_triggers_satisfied(quest, satisfied_location_ids):
        return active_quest_id
    return None


def _location_triggers_satisfied(quest, satisfied_location_ids: set[str]) -> bool:
    triggers = quest_triggers(quest)
    if not triggers or quest_choices(quest):
        return False
    return all(
        trigger.get("type") == "location_enter"
        and trigger.get("target") in satisfied_location_ids
        for trigger in triggers
    )
