"""state_change `set` permission matrix.

Single source for `engines/apply.py` (which enforces forbidden fields per
change) and `agents/narrate/runner.py` (which renders these into the narrate
prompt at load time so the LLM sees the same list the engine will reject
against).

The two used to be hand-mirrored: `gender` and `location_id` had been added
to the prompt but not the engine's frozenset, leaving a `set field=location_id`
route around the dedicated `move` change kind. Centralizing closes that.

Order in the *_ORDERED tuples is the order the prompt prints; group by stat
block, list-typed engine state, death tracking, then identity. The frozenset
is derived — only edit the tuple.
"""

from __future__ import annotations

CHAR_FORBIDDEN_ORDERED: tuple[str, ...] = (
    "hp",
    "max_hp",
    "mp",
    "max_mp",
    "xp_pool",
    "xp_reward",
    "gold",
    "level",
    "alive",
    "relations",
    "inventory_ids",
    "memories",
    "learned_skill_ids",
    "racial_skill_ids",
    "companions",
    "active_buffs",
    "hints",
    "death_saves",
    "revive_coins",
    "id",
    "is_player",
    "race_id",
    "gender",
    "location_id",
)
ITEM_FORBIDDEN_ORDERED: tuple[str, ...] = ("id", "effects", "required")
LOC_FORBIDDEN_ORDERED: tuple[str, ...] = (
    "id",
    "item_ids",
    "hidden_items",
    "connections",
    "hidden_connections",
    "sleep_encounters",
)
CHAPTER_QUEST_ALLOWED_ORDERED: tuple[str, ...] = ("summary", "status")

CHAR_FORBIDDEN = frozenset(CHAR_FORBIDDEN_ORDERED)
ITEM_FORBIDDEN = frozenset(ITEM_FORBIDDEN_ORDERED)
LOC_FORBIDDEN = frozenset(LOC_FORBIDDEN_ORDERED)
CHAPTER_QUEST_ALLOWED = frozenset(CHAPTER_QUEST_ALLOWED_ORDERED)

FORBIDDEN_BY_ENTITY: dict[str, frozenset[str]] = {
    "characters": CHAR_FORBIDDEN,
    "items": ITEM_FORBIDDEN,
    "locations": LOC_FORBIDDEN,
}


def render_for_prompt() -> dict[str, str]:
    """Slash-joined forbidden lists keyed for narrate prompt placeholder
    substitution (`{{CHAR_FORBIDDEN}}` etc.). Identity-only fields (`id`)
    are dropped — they're universally forbidden and only add prompt noise."""

    def _render(t: tuple[str, ...]) -> str:
        return "/".join(f for f in t if f != "id")

    return {
        "CHAR_FORBIDDEN": _render(CHAR_FORBIDDEN_ORDERED),
        "ITEM_FORBIDDEN": _render(ITEM_FORBIDDEN_ORDERED),
        "LOC_FORBIDDEN": _render(LOC_FORBIDDEN_ORDERED),
    }
