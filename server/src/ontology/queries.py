"""Named traversals over `GameGraph`.

Hides edge-type strings — call sites read the intent (`inventory_of`,
`inhabitants_of`) instead of the underlying edge label. Keeps the relational
SSOT rule (CLAUDE.md) intact: anything asking who-relates-to-whom goes
through the graph, just via a named function.

Returns:
- `list[str]` for traversals where the caller never inspects edge attrs.
- `list[Edge]` for traversals where attrs matter (`equips.slot`,
  `knows_skill.source`, `connects_to.difficulty/key_item_id`).
- `str | None` for single-valued relations (race, quest giver, chapter).
"""

from .graph import Edge, GameGraph


# --- location -------------------------------------------------------------


def inhabitants_of(graph: GameGraph, location_id: str) -> list[str]:
    """Character IDs whose `located_at` edge points to this location."""
    return [e.from_id for e in graph.get_in_edges(location_id, "located_at")]


def items_in(graph: GameGraph, location_id: str) -> list[str]:
    """Item IDs `located_in` this location."""
    return [e.from_id for e in graph.get_in_edges(location_id, "located_in")]


def container_of(graph: GameGraph, item_id: str) -> str | None:
    """Location ID containing this item (`located_in`), or None.

    Items in characters' inventories are tracked via `carries`, not this edge —
    `container_of` only resolves items stashed in a location.
    """
    for e in graph.get_edges(item_id, "located_in"):
        return e.to_id
    return None


def connections_of(graph: GameGraph, location_id: str) -> list[Edge]:
    """`connects_to` edges out of this location.

    Edge.attrs holds `difficulty` and `key_item_id` when present.
    """
    return graph.get_edges(location_id, "connects_to")


# --- character composition ------------------------------------------------


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


# --- quests ---------------------------------------------------------------


def quests_given_by(graph: GameGraph, char_id: str) -> list[str]:
    """Quest IDs this character gives."""
    return [e.to_id for e in graph.get_edges(char_id, "gives_quest")]


def giver_of(graph: GameGraph, quest_id: str) -> str | None:
    """Character ID who gives this quest, or None."""
    for e in graph.get_in_edges(quest_id, "gives_quest"):
        return e.from_id
    return None


def kill_targets_of(graph: GameGraph, quest_id: str) -> list[str]:
    """Character IDs whose death advances this quest (strict subset of
    `trigger_targets_of`)."""
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


# --- items ----------------------------------------------------------------


def locations_unlocked_by(graph: GameGraph, item_id: str) -> list[str]:
    """Location IDs this item unlocks (key item → connection target)."""
    return [e.to_id for e in graph.get_edges(item_id, "unlocks")]


# --- chapters -------------------------------------------------------------


def chapter_of_quest(graph: GameGraph, quest_id: str) -> str | None:
    """Chapter ID this quest belongs to, or None."""
    for e in graph.get_edges(quest_id, "member_of_chapter"):
        return e.to_id
    return None


def quests_in_chapter(graph: GameGraph, chapter_id: str) -> list[str]:
    """Quest IDs that are members of this chapter."""
    return [e.from_id for e in graph.get_in_edges(chapter_id, "member_of_chapter")]
