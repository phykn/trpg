from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import Graph, SetNodePropertyChange


class GraphProgressionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[SetNodePropertyChange]
    next_active_quest_id: str | None
    completed_chapter_ids: list[str]
    scenario_completed: bool = False


def plan_progression_after_quest_completion(
    graph: Graph,
    *,
    completed_quest_ids: list[str],
    active_quest_id: str | None,
) -> GraphProgressionResult:
    statuses = {
        node_id: _node_status(node)
        for node_id, node in graph.nodes.items()
        if node.type in {"quest", "chapter"}
    }
    changes: list[SetNodePropertyChange] = []
    completed_chapter_ids: list[str] = []
    completed = set(completed_quest_ids)
    next_active_quest_id = None if active_quest_id in completed else active_quest_id

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

    for chapter_id in _chapter_ids(graph):
        if status(chapter_id) == "locked" and _prerequisites_met(graph, chapter_id, status):
            set_status(chapter_id, "active")

    if next_active_quest_id is None:
        for quest_id in _quest_ids(graph):
            if status(quest_id) != "pending":
                continue
            if not _is_required_quest(graph, quest_id):
                continue
            if not _prerequisites_met(graph, quest_id, status):
                continue
            set_status(quest_id, "active")
            next_active_quest_id = quest_id
            break

    for quest_id in _quest_ids(graph):
        if status(quest_id) != "locked":
            continue
        if not _prerequisite_ids(graph, quest_id):
            continue
        if not _prerequisites_met(graph, quest_id, status):
            continue
        if not _is_required_quest(graph, quest_id):
            set_status(quest_id, "pending")
            continue
        if next_active_quest_id is None:
            set_status(quest_id, "active")
            next_active_quest_id = quest_id
        else:
            set_status(quest_id, "pending")

    required_quest_ids = [
        quest_id for quest_id in _quest_ids(graph) if _is_required_quest(graph, quest_id)
    ]
    scenario_completed = bool(required_quest_ids) and all(
        status(quest_id) == "completed" for quest_id in required_quest_ids
    )

    return GraphProgressionResult(
        changes=changes,
        next_active_quest_id=next_active_quest_id,
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


def _prerequisites_met(graph: Graph, node_id: str, status) -> bool:
    return all(status(prereq_id) == "completed" for prereq_id in _prerequisite_ids(graph, node_id))


def _prerequisite_ids(graph: Graph, node_id: str) -> list[str]:
    node = graph.nodes[node_id]
    raw = node.properties.get("prerequisites", [])
    return [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []
