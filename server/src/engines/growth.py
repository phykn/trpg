"""Growth: level_up, pair-trade, xp curve. Pair-trade invariant — total stats = 60, pair sums permanently 20/20/20."""

from __future__ import annotations

from ..domain.entities import Character
from ..domain.state import GameState
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
        raise LevelUpInvalid(f"not enough xp: have {character.xp_pool}, need {cost}")

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


def xp_for_grade(grade: str) -> int:
    """Per-roll xp award by grade (RULES.growth.roll_xp). Unknown grade → 0."""
    return RULES.growth.roll_xp.get(grade, 0)


def grant_roll_xp(
    state: GameState,
    grade: str,
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> int:
    """Award per-grade roll xp to the player. Returns the amount granted."""
    amount = xp_for_grade(grade)
    if amount <= 0:
        return 0
    player = state.characters.get(state.player_id)
    if player is None:
        return 0
    grant_xp(player, amount, dirty=dirty)
    return amount


def award_kill_xp(
    state: GameState,
    killer_id: str,
    victim_id: str,
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> int:
    """When `killer_id` lands the killing blow on `victim_id`, transfer
    `victim.xp_reward` to the killer's xp_pool. Returns the amount granted.
    Non-player killers and zero-reward victims are no-ops."""
    if killer_id != state.player_id:
        return 0
    victim = state.characters.get(victim_id)
    killer = state.characters.get(killer_id)
    if victim is None or killer is None:
        return 0
    amount = victim.xp_reward
    if amount <= 0:
        return 0
    grant_xp(killer, amount, dirty=dirty)
    return amount
