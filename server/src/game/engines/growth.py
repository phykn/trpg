"""Shared graph progression formulas."""

from ..rules import RULES


def xp_for_next_level(level: int) -> int:
    if level >= RULES.growth.max_level:
        return 0
    return RULES.growth.base_xp * max(level, 1)


def calc_max_hp(level: int, con: int | None = None) -> int:
    del con
    return min(10, 4 + max(level, 1))


def calc_max_mp(level: int, int_: int | None = None) -> int:
    del int_
    return min(10, 4 + max(level, 1))
