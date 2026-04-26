import math
import random

from ..domain.entities import Character
from ..domain.types import Grade, Tier
from ..rules import RULES

_TIER_ORDER: tuple[Tier, ...] = (
    "매우 쉬움",
    "쉬움",
    "보통",
    "어려움",
    "매우 어려움",
    "전설",
    "신화",
)


def tier_to_int(tier: Tier) -> int:
    return _TIER_ORDER.index(tier) + 1


def int_to_tier(value: int) -> Tier:
    return _TIER_ORDER[value - 1]


def pick_dc(tier: Tier, rng: random.Random | None = None) -> int:
    lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
    return (rng or random).randint(lo, hi)


def sigmoid_required_roll(dc: int, stat: int, k: float | None = None) -> int:
    if k is None:
        k = RULES.difficulty_class.sigmoid.k
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
    # Critical 은 원본 dice 만 봄 — mod 가 critical 을 만들거나 지울 수 없음.
    if dice >= RULES.difficulty_class.critical_hit_threshold:
        return "critical_success"
    if dice <= RULES.difficulty_class.critical_miss_threshold:
        return "critical_failure"
    if total > required_roll:
        return "success"
    if total == required_roll:
        return "partial_success"
    return "failure"
