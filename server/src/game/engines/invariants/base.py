"""Base types and helpers shared across invariant sub-modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    """Seed bundle or runtime state projection. runtime=True relaxes seed-only rules so check_state can reuse the same machinery."""

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

    @classmethod
    def from_state(cls, state: Any) -> "Scenario":
        player = state.characters.get(state.player_id)
        return cls(
            races=dict(state.races),
            locations=dict(state.locations),
            items=dict(state.items),
            skills=dict(state.skills),
            characters=dict(state.characters),
            quests=dict(state.quests),
            chapters=dict(state.chapters),
            start={
                "start_location_id": player.location_id if player else None,
                "active_subject_id": state.active_subject_id,
                "active_quest_id": state.active_quest_id,
            },
            player_template={},
            runtime=True,
        )


def _v(out: list[str], where: str, msg: str) -> None:
    out.append(f"[{where}] {msg}")
