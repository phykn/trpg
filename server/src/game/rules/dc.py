import random

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
