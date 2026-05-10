"""Game-rule invariants. Each check_* returns list[str]; one-line messages are fed back to the LLM verbatim as self-correction feedback."""

from .base import InvariantViolation, Scenario
from .character import check_character, check_seed_character, check_skills, check_stats
from .item import check_inventory, check_item
from .scenario import check_chapter_graph, check_quest_graph, check_scenario

__all__ = [
    "InvariantViolation",
    "Scenario",
    "check_chapter_graph",
    "check_character",
    "check_inventory",
    "check_item",
    "check_quest_graph",
    "check_scenario",
    "check_seed_character",
    "check_skills",
    "check_stats",
]
