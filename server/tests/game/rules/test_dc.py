import random

from src.game.rules.dc import (
    compute_grade,
    compute_required_roll,
    pick_dc,
)
from src.game.rules import RULES


def test_pick_dc_within_range_excludes_bounds():
    rng = random.Random(0)
    for tier in ("very_easy", "easy", "normal", "hard", "very_hard", "legend", "myth"):
        lo, hi = RULES.difficulty_class.tier_dc_ranges[tier]
        for _ in range(50):
            dc = pick_dc(tier, rng)
            assert lo <= dc <= hi
            assert 1 < dc < 20


def test_required_roll_stat_ten_is_neutral():
    # Stat 10/11 → mod 0 → required == DC across the range.
    for dc in (2, 7, 10, 13, 18):
        assert compute_required_roll(dc=dc, stat=10) == dc
        assert compute_required_roll(dc=dc, stat=11) == dc


def test_required_roll_dnd5e_modifier_applied():
    # required = DC - stat_mod. floor((stat-10)/2): 12→+1, 14→+2, 8→-1, 6→-2.
    assert compute_required_roll(dc=15, stat=12) == 14
    assert compute_required_roll(dc=15, stat=14) == 13
    assert compute_required_roll(dc=15, stat=8) == 16
    assert compute_required_roll(dc=15, stat=6) == 17


def test_required_roll_clamps_to_one_or_twenty():
    assert compute_required_roll(dc=5, stat=20) == 1  # 5 - 5 = 0 → clamp 1
    assert compute_required_roll(dc=19, stat=0) == 20  # 19 - (-5) = 24 → clamp 20


def test_compute_grade_critical_priority():
    assert compute_grade(dice=20, total=20, required_roll=18) == "critical_success"
    assert compute_grade(dice=20, total=10, required_roll=18) == "critical_success"
    assert compute_grade(dice=1, total=15, required_roll=10) == "critical_failure"


def test_compute_grade_normal_branches():
    # total >= required → success (boundary inclusive, matching "DC 이상이면 성공" convention).
    assert compute_grade(dice=15, total=18, required_roll=15) == "success"
    assert compute_grade(dice=10, total=10, required_roll=10) == "success"
    # Missing by exactly 1 is failure.
    assert compute_grade(dice=10, total=9, required_roll=10) == "failure"
    assert compute_grade(dice=5, total=5, required_roll=10) == "failure"
