from .graph import Edge, GameGraph


def inhabitants_of(graph: GameGraph, location_id: str) -> list[str]:
    """Character IDs whose `located_at` edge points to this location."""
    return [e.from_id for e in graph.get_in_edges(location_id, "located_at")]


def items_in(graph: GameGraph, location_id: str) -> list[str]:
    """Item IDs `located_in` this location."""
    return [e.from_id for e in graph.get_in_edges(location_id, "located_in")]


def container_of(graph: GameGraph, item_id: str) -> str | None:
    """Location ID containing this item (`located_in`), or None. Inventory items use `carries` instead."""
    for e in graph.get_edges(item_id, "located_in"):
        return e.to_id
    return None


def connections_of(graph: GameGraph, location_id: str) -> list[Edge]:
    """`connects_to` edges out of this location. `attrs.difficulty` / `attrs.key_item_id` may be set."""
    return graph.get_edges(location_id, "connects_to")


def race_of(graph: GameGraph, char_id: str) -> str | None:
    """Race ID this character belongs to, or None."""
    for e in graph.get_edges(char_id, "belongs_to_race"):
        return e.to_id
    return None


def location_of(graph: GameGraph, char_id: str) -> str | None:
    """Location ID this character is at (`located_at`), or None."""
    for e in graph.get_edges(char_id, "located_at"):
        return e.to_id
    return None


def equipment_of(graph: GameGraph, char_id: str) -> list[Edge]:
    """`equips` edges. `Edge.attrs.slot` identifies the slot."""
    return graph.get_edges(char_id, "equips")


def inventory_of(graph: GameGraph, char_id: str) -> list[str]:
    """Item IDs this character carries (raw, may include duplicates)."""
    return [e.to_id for e in graph.get_edges(char_id, "carries")]


def known_skills_of(graph: GameGraph, char_id: str) -> list[Edge]:
    """`knows_skill` edges. `Edge.attrs.source` is `'racial'` | `'learned'`."""
    return graph.get_edges(char_id, "knows_skill")


def companions_of(graph: GameGraph, char_id: str) -> list[str]:
    """Companion character IDs."""
    return [e.to_id for e in graph.get_edges(char_id, "has_companion")]


def quests_given_by(graph: GameGraph, char_id: str) -> list[str]:
    """Quest IDs this character gives."""
    return [e.to_id for e in graph.get_edges(char_id, "gives_quest")]


def giver_of(graph: GameGraph, quest_id: str) -> str | None:
    """Character ID who gives this quest, or None."""
    for e in graph.get_in_edges(quest_id, "gives_quest"):
        return e.from_id
    return None


def kill_targets_of(graph: GameGraph, quest_id: str) -> list[str]:
    """Character IDs whose death advances this quest (strict subset of `trigger_targets_of`)."""
    return [e.from_id for e in graph.get_in_edges(quest_id, "kill_target_of")]


def quests_killing(graph: GameGraph, char_id: str) -> list[str]:
    """Quest IDs where killing this character is a trigger."""
    return [e.to_id for e in graph.get_edges(char_id, "kill_target_of")]


def trigger_targets_of(graph: GameGraph, quest_id: str) -> list[str]:
    """All trigger target IDs for this quest. Includes the kill_target subset."""
    return [e.from_id for e in graph.get_in_edges(quest_id, "required_by")]


def quests_requiring(graph: GameGraph, char_id: str) -> list[str]:
    """Quest IDs this character is a trigger target of."""
    return [e.to_id for e in graph.get_edges(char_id, "required_by")]


def reward_items_of(graph: GameGraph, quest_id: str) -> list[str]:
    """Item IDs given as quest rewards."""
    return [e.from_id for e in graph.get_in_edges(quest_id, "reward_of")]


def quests_rewarding(graph: GameGraph, item_id: str) -> list[str]:
    """Quest IDs that award this item."""
    return [e.to_id for e in graph.get_edges(item_id, "reward_of")]


def locations_unlocked_by(graph: GameGraph, item_id: str) -> list[str]:
    """Location IDs this item unlocks (key item → connection target)."""
    return [e.to_id for e in graph.get_edges(item_id, "unlocks")]


def quests_in_chapter(graph: GameGraph, chapter_id: str) -> list[str]:
    """Quest IDs that are members of this chapter."""
    return [e.from_id for e in graph.get_in_edges(chapter_id, "member_of_chapter")]
