from typing import Any

from .graph import GraphNode


def quest_triggers(quest: GraphNode) -> list[dict[str, Any]]:
    triggers = quest.properties.get("triggers", [])
    if not isinstance(triggers, list):
        return []
    return [trigger for trigger in triggers if isinstance(trigger, dict)]


def quest_choices(quest: GraphNode) -> dict[str, dict[str, Any]]:
    choices = quest.properties.get("choices")
    if not isinstance(choices, dict):
        return {}
    return {
        key: value
        for key, value in choices.items()
        if isinstance(key, str) and key and isinstance(value, dict)
    }


def quest_triggers_met(quest: GraphNode, total: int | None = None) -> list[bool]:
    total = len(quest_triggers(quest)) if total is None else total
    raw = quest.properties.get("triggers_met", [])
    values = raw if isinstance(raw, list) else []
    padded = [*values[:total], *([False] * max(0, total - len(values)))]
    return [item if isinstance(item, bool) else False for item in padded]


def quest_progress(quest: GraphNode) -> tuple[int, int]:
    triggers = quest_triggers(quest)
    met = quest_triggers_met(quest, len(triggers))
    return sum(1 for item in met if item is True), len(triggers)


def quest_ready_to_decide(quest: GraphNode) -> bool:
    done, total = quest_progress(quest)
    return total == 0 or done >= total


def is_required_quest(quest: GraphNode) -> bool:
    explicit = quest.properties.get("required")
    if explicit is True:
        return True
    if explicit is False:
        return False
    return not _is_generated_quest_beat(quest)


def _is_generated_quest_beat(quest: GraphNode) -> bool:
    return isinstance(quest.properties.get("turn_id"), int) and quest.properties.get(
        "stability"
    ) in {"scene", "chapter", "campaign"}
