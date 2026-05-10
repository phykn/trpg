"""Base types and helpers shared across invariant sub-modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.entities import (
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)


class InvariantViolation(ValueError):
    pass


def _slot_mismatch_hint(allowed: tuple[str, ...]) -> str:
    if not allowed:
        return "consumable, cannot be equipped"
    if allowed == ("weapon",):
        return "weapon, must be in the weapon slot"
    if "armor" in allowed and "accessory" in allowed:
        return "defense item, must be in the armor or accessory slot"
    return "decorative, must be in the accessory slot"


@dataclass
class Scenario:
    """Seed bundle. runtime=True relaxes seed-only rules for runtime projections."""

    races: dict[str, Race] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    characters: dict[str, Character] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    chapters: dict[str, Chapter] = field(default_factory=dict)
    start: dict = field(default_factory=dict)
    player_template: dict = field(default_factory=dict)
    runtime: bool = False

def _v(out: list[str], where: str, msg: str) -> None:
    out.append(f"[{where}] {msg}")
