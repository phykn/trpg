"""성장 (level_up + 페어 트레이드 + xp 곡선).

docs/03-features.md §2.3.

페어 트레이드 불변식: 캐릭터의 stat 합 = 60 (시작), 페어 합 = 20/20/20 영구. NPC 시드든
LLM 즉석 캐릭터든 모두 따른다.
"""
from __future__ import annotations

from typing import Literal

from ..domain.entities import Character
from ..domain.types import StatKey
from ..domain.errors import LevelUpInvalid
from ..rules import RULES

# 페어: 정반대 (양방향). stat_up 키 → 깎아야 하는 stat.
PAIR_TRADE: dict[StatKey, StatKey] = {
    "STR": "CHA",
    "CHA": "STR",
    "DEX": "WIS",
    "WIS": "DEX",
    "CON": "INT",
    "INT": "CON",
}


def xp_for_next_level(level: int) -> int:
    """레벨 N → N+1 비용 = base_xp × N (선형). level=0 은 base_xp 1배."""
    if level >= RULES.growth.max_level:
        return 0
    n = max(level, 1)  # 0→1 은 base_xp × 1, 1→2 는 ×1, 2→3 은 ×2, ...
    return RULES.growth.base_xp * n


def calc_max_hp(level: int, con: int) -> int:
    return (10 + con) + level * (5 + con // 4)


def calc_max_mp(level: int, int_: int) -> int:
    return (5 + int_) + level * (3 + int_ // 4)


def recalc_max_hp_mp(character: Character) -> None:
    """현재 level/CON/INT 로 max 재계산. 현재값이 새 max 보다 크면 clamp."""
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
    """xp 차감 + 레벨 +1 + 페어 트레이드 + HP/MP max 재계산.

    검증 실패 시 LevelUpInvalid raise. 부분 적용 안 함 (xp 도 안 깎음).
    """
    if character.level >= RULES.growth.max_level:
        raise LevelUpInvalid(f"already at max level {RULES.growth.max_level}")

    cost = xp_for_next_level(character.level)
    if character.xp_pool < cost:
        raise LevelUpInvalid(
            f"not enough xp: have {character.xp_pool}, need {cost}"
        )

    expected_down = PAIR_TRADE.get(stat_up)
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
    """STR+CHA = 20, DEX+WIS = 20, CON+INT = 20 검증.

    LLM 즉석 캐릭터 등록 시 호출. 시드 검증·테스트 도구. 실패 시 ValueError.
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
    """xp_pool 에 가산. 자동 레벨업은 안 함 (docs §2.3 — 명시적 endpoint 호출)."""
    if amount < 0:
        raise ValueError(f"xp grant must be non-negative, got {amount}")
    character.xp_pool += amount
    if dirty is not None:
        dirty.add(("characters", character.id))


# Re-export for type-narrowing in tests / endpoints.
StatLiteral = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]
