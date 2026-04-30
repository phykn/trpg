import math
import random

from ..domain.entities import Character
from ..domain.types import Grade, Tier
from .config import RULES


def pick_dc(tier: Tier, rng: random.Random | None = None) -> int:
    lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
    return (rng or random).randint(lo, hi)


def tier_mid_dc(tier: Tier) -> int:
    """Deterministic mid-range DC for a tier. Used when the call site needs
    a stable DC without threading rng (e.g. arming a pending_check whose
    actual roll target gets recomputed in /roll)."""
    lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
    return (lo + hi) // 2


def sigmoid_required_roll(dc: int, stat: int) -> int:
    k = RULES.difficulty_class.sigmoid_k
    raw = 20 / (1 + math.exp(-k * (dc - stat)))
    return max(1, min(20, round(raw)))


def social_bonus(actor: Character, target_id: str) -> int:
    aff = actor.relations.get(target_id, 0)
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
    if total > required_roll:
        return "success"
    if total == required_roll:
        return "partial_success"
    return "failure"
