"""Shared graph progression formulas."""

from ..rules import RULES


def xp_for_next_level(level: int) -> int:
    if level >= RULES.growth.max_level:
        return 0
    return RULES.growth.base_xp * max(level, 1)


def calc_max_hp(level: int, con: int) -> int:
    return (10 + con) + level * (5 + con // 4)


def calc_max_mp(level: int, int_: int) -> int:
    return (5 + int_) + level * (3 + int_ // 4)
