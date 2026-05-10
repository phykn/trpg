from typing import Any

from src.game.domain.graph import Graph, GraphChange, GraphNode
from src.game.engines.graph_quest_common import (
    GraphQuestProgressResult,
    property_change,
    quest_status,
    status_change,
)


def plan_quest_progress_for_character_defeat(
    graph: Graph,
    character_id: str,
) -> GraphQuestProgressResult:
    changes: list[GraphChange] = []
    completed_quest_ids: list[str] = []
    for quest in graph.nodes.values():
        if quest.type != "quest" or quest_status(quest) != "active":
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
        changes.append(property_change(quest.id, "triggers_met", triggers_met))
        if triggers and all(triggers_met):
            changes.append(status_change(quest.id, "completed"))
            completed_quest_ids.append(quest.id)
    return GraphQuestProgressResult(
        changes=changes,
        completed_quest_ids=completed_quest_ids,
    )


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
