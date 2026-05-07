import random

from ..domain.entities import Character
from ..domain.types import Grade, Tier
from .config import RULES


def pick_dc(tier: Tier, rng: random.Random | None = None) -> int:
    lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
    return (rng or random).randint(lo, hi)


def compute_required_roll(dc: int, stat: int) -> int:
    """D&D 5e: required = DC - stat_modifier, where stat_modifier = floor((stat-10)/2).
    Stat 10/11 → required = DC (no shift). Clamped to [1, 20]."""
    mod = (stat - 10) // 2
    return max(1, min(20, dc - mod))


def social_bonus(target: Character, actor_id: str) -> int:
    """Roll bonus based on how the *target* views the actor.

    `target` holds the relations dict (the NPC the actor is rolling against);
    `actor_id` is who's making the roll. A trusted persuader gets +bonus, a
    despised one gets -bonus, neutral 0. This direction matches the rest of
    the affinity system — only `npc.relations[player]` is tracked.
    """
    aff = target.relations.get(actor_id, 0)
    threshold = RULES.social.friendly_threshold
    bonus = RULES.social.roll_bonus
    if aff >= threshold:
        return bonus
    if aff <= -threshold:
        return -bonus
    return 0


def compute_grade(dice: int, total: int, required_roll: int) -> Grade:
    # Critical only looks at the raw dice — mod cannot create or erase a critical.
    if dice >= RULES.difficulty_class.critical_hit_threshold:
        return "critical_success"
    if dice <= RULES.difficulty_class.critical_miss_threshold:
        return "critical_failure"
    if total >= required_roll:
        return "success"
    if total == required_roll - 1:
        return "partial_success"
    return "failure"
