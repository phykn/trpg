"""state_change `set` permission matrix — single source for the engine's forbidden-field check and the narrate prompt's rendered list. Edit the tuple; the frozenset derives."""

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


def render_for_prompt(locale: str) -> dict[str, str]:
    """Forbidden-field substitution dict; locale reserved for Tasks 13-14."""

    def _render(t: tuple[str, ...]) -> str:
        return "/".join(f for f in t if f != "id")

    del locale  # placeholder until narrate catalog keys exist
    return {
        "CHAR_FORBIDDEN": _render(CHAR_FORBIDDEN_ORDERED),
        "ITEM_FORBIDDEN": _render(ITEM_FORBIDDEN_ORDERED),
        "LOC_FORBIDDEN": _render(LOC_FORBIDDEN_ORDERED),
    }
