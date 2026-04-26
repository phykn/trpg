import random

from src.domain.entities import Character, Stats
from src.pipeline.dc import (
    compute_grade,
    int_to_tier,
    pick_dc,
    sigmoid_required_roll,
    social_bonus,
    tier_to_int,
)
from src.rules import RULES


def test_tier_int_round_trip():
    for value in range(1, 8):
        assert tier_to_int(int_to_tier(value)) == value


def test_pick_dc_within_range_excludes_bounds():
    rng = random.Random(0)
    for tier in ("매우 쉬움", "쉬움", "보통", "어려움", "매우 어려움", "전설", "신화"):
        lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
        for _ in range(50):
            dc = pick_dc(tier, rng)
            assert lo <= dc <= hi
            assert 1 < dc < 20


def test_sigmoid_balance_point():
    # stat == dc → required = 10
    assert sigmoid_required_roll(dc=10, stat=10) == 10


def test_sigmoid_clamps_to_one_or_twenty():
    assert sigmoid_required_roll(dc=5, stat=15) == 1
    assert sigmoid_required_roll(dc=15, stat=5) == 20


def test_sigmoid_monotonic():
    prev = sigmoid_required_roll(dc=10, stat=10)
    for d in range(11, 16):
        cur = sigmoid_required_roll(dc=d, stat=10)
        assert cur >= prev
        prev = cur


def test_social_bonus_thresholds():
    ch = Character(
        id="p", name="x", race_id="human", stats=Stats(),
        relations={"friend": 70, "foe": -60, "neutral": 10},
    )
    assert social_bonus(ch, "friend") == RULES.social.roll_bonus
    assert social_bonus(ch, "foe") == -RULES.social.roll_bonus
    assert social_bonus(ch, "neutral") == 0
    assert social_bonus(ch, "unknown") == 0


def test_compute_grade_critical_priority():
    assert compute_grade(dice=20, total=20, required_roll=18) == "critical_success"
    assert compute_grade(dice=20, total=10, required_roll=18) == "critical_success"
    assert compute_grade(dice=1, total=15, required_roll=10) == "critical_failure"


def test_compute_grade_normal_branches():
    assert compute_grade(dice=15, total=18, required_roll=15) == "success"
    assert compute_grade(dice=10, total=10, required_roll=10) == "partial_success"
    assert compute_grade(dice=5, total=5, required_roll=10) == "failure"
