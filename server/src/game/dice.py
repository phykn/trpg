"""Twenty-sided checks for authored choices."""

from typing import Literal

Grade = Literal["critical_success", "success", "failure", "critical_failure"]


def compute_required_roll(dc: int, stat: int) -> int:
    modifier = (stat - 10) // 2
    return max(1, min(20, dc - modifier))


def compute_grade(dice: int, total: int, required_roll: int) -> Grade:
    if dice >= 20:
        return "critical_success"
    if dice <= 1:
        return "critical_failure"
    return "success" if total >= required_roll else "failure"
