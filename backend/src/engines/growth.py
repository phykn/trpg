"""Growth (level_up + pair-trade + xp curve).

docs/03-features.md §2.3.

Pair-trade invariant: a character's total stats = 60 (initial), with pair sums permanently
20/20/20. Holds for both seeded NPCs and LLM-summoned characters.
"""
from __future__ import annotations

from ..domain.entities import Character
from ..domain.types import STAT_PAIRS, StatKey
from ..domain.errors import LevelUpInvalid
from ..rules import RULES


def xp_for_next_level(level: int) -> int:
    """Cost from level N → N+1 = base_xp × N (linear). level=0 costs 1× base_xp."""
    if level >= RULES.growth.max_level:
        return 0
    n = max(level, 1)  # 0→1 is base_xp × 1, 1→2 is ×1, 2→3 is ×2, ...
    return RULES.growth.base_xp * n


def calc_max_hp(level: int, con: int) -> int:
    return (10 + con) + level * (5 + con // 4)


def calc_max_mp(level: int, int_: int) -> int:
    return (5 + int_) + level * (3 + int_ // 4)


def recalc_max_hp_mp(character: Character) -> None:
    """Recompute max from current level/CON/INT. Clamps current values down to the new max if they exceed it."""
    new_max_hp = calc_max_hp(character.level, character.stats.CON)
    new_max_mp = calc_max_mp(character.level, character.stats.INT)
    character.max_hp = new_max_hp
    character.max_mp = new_max_mp
    if character.hp > new_max_hp:
        character.hp = new_max_hp
    if character.mp > new_max_mp:
        character.mp = new_max_mp


def can_afford_level_up(character: Character) -> bool:
    if character.level >= RULES.growth.max_level:
        return False
    return character.xp_pool >= xp_for_next_level(character.level)


def level_up(
    character: Character,
    stat_up: StatKey,
    stat_down: StatKey,
) -> None:
    """Deduct xp, level +1, apply pair-trade, recompute HP/MP max.

    Raises LevelUpInvalid on validation failure. No partial application (xp is not debited).
    """
    if character.level >= RULES.growth.max_level:
        raise LevelUpInvalid(f"already at max level {RULES.growth.max_level}")

    cost = xp_for_next_level(character.level)
    if character.xp_pool < cost:
        raise LevelUpInvalid(
            f"not enough xp: have {character.xp_pool}, need {cost}"
        )

    expected_down = STAT_PAIRS.get(stat_up)
    if expected_down is None:
        raise LevelUpInvalid(f"invalid stat_up: {stat_up}")
    if stat_down != expected_down:
        raise LevelUpInvalid(
            f"stat_down must be {expected_down} when stat_up={stat_up} (got {stat_down})"
        )

    up_value = getattr(character.stats, stat_up)
    down_value = getattr(character.stats, stat_down)
    if up_value >= 20:
        raise LevelUpInvalid(f"{stat_up} already at cap 20")
    if down_value <= 0:
        raise LevelUpInvalid(f"{stat_down} already at 0 — pair-trade blocked")

    character.xp_pool -= cost
    character.level += 1
    setattr(character.stats, stat_up, up_value + 1)
    setattr(character.stats, stat_down, down_value - 1)
    recalc_max_hp_mp(character)


def assert_pair_trade_invariant(character: Character) -> None:
    """Verify STR+CHA = 20, DEX+WIS = 20, CON+INT = 20.

    Called when registering an LLM-summoned character. Also used for seed validation and
    in tests. Raises ValueError on failure.
    """
    s = character.stats
    if s.STR + s.CHA != 20:
        raise ValueError(
            f"pair-trade invariant violated: STR({s.STR}) + CHA({s.CHA}) != 20"
        )
    if s.DEX + s.WIS != 20:
        raise ValueError(
            f"pair-trade invariant violated: DEX({s.DEX}) + WIS({s.WIS}) != 20"
        )
    if s.CON + s.INT != 20:
        raise ValueError(
            f"pair-trade invariant violated: CON({s.CON}) + INT({s.INT}) != 20"
        )


def grant_xp(
    character: Character,
    amount: int,
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> None:
    """Add to xp_pool. No automatic level-up (docs §2.3 — explicit endpoint call required)."""
    if amount < 0:
        raise ValueError(f"xp grant must be non-negative, got {amount}")
    character.xp_pool += amount
    if dirty is not None:
        dirty.add(("characters", character.id))
