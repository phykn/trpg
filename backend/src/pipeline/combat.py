"""전투 엔진 코어 — LLM 호출 없는 순수 룰.

호출자 (pipeline/turn.py) 가 라운드 진행을 지휘하고, 이 모듈은 한 번의 명중·데미지·AI 결정·flee 시도 같은 결정론적 단위를 노출한다.
공식 출처: docs/03-features.md §1.1-§1.6.
"""
from __future__ import annotations

import random
import re
from typing import Literal

from pydantic import BaseModel

from ..domain.entities import (
    ArmorEffect,
    Character,
    CombatBehavior,
    CombatState,
    DeathSaveState,
    Item,
    WeaponEffect,
)
from ..domain.types import Grade, StatKey
from ..rules import RULES
from ..state.models import GameState
from .dc import compute_grade, sigmoid_required_roll


# --- 공용 ---------------------------------------------------------------------


_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")
_ARMOR_SLOTS: tuple[str, ...] = ("head", "top", "bottom", "feet")


def stat_modifier(stat_value: int) -> int:
    """D&D 5e: floor((stat - 10) / 2). 10 → 0, 0 → -5, 20 → +5."""
    return (stat_value - 10) // 2


def roll_dice(spec: str, rng: random.Random | None = None) -> int:
    """`1d8`, `2d6+3`, `1d4-1` 형식 굴려 합 반환."""
    m = _DICE_RE.match(spec)
    if not m:
        raise ValueError(f"invalid dice spec: {spec!r}")
    n, sides = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    r = rng or random
    return sum(r.randint(1, sides) for _ in range(n)) + bonus


def _dice_count_and_sides(spec: str) -> tuple[int, int, int]:
    """spec → (n, sides, bonus). 크리티컬 데미지 굴림 (다이스 두 번 + bonus 한 번) 용."""
    m = _DICE_RE.match(spec)
    if not m:
        raise ValueError(f"invalid dice spec: {spec!r}")
    n, sides = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    return n, sides, bonus


# --- 무기·방어 사영 -----------------------------------------------------------


class _Weapon(BaseModel):
    """공격 굴림 1 회를 위한 무기 사영 — 실제 Item 또는 unarmed 폴백."""
    item_id: str | None  # None = unarmed
    dice: str
    range_m: float
    two_handed: bool


def _unarmed_weapon() -> _Weapon:
    u = RULES.combat.unarmed
    return _Weapon(item_id=None, dice=u.damage, range_m=u.range_m, two_handed=False)


def _weapon_for_slot(slot_id: str | None, items: dict[str, Item]) -> _Weapon | None:
    """장비 슬롯 → 무기 사영. 비어 있거나 무기 아니면 None."""
    if slot_id is None:
        return None
    item = items.get(slot_id)
    if item is None or item.effects is None:
        return None
    if not isinstance(item.effects, WeaponEffect):
        return None
    eff = item.effects
    return _Weapon(
        item_id=item.id,
        dice=eff.weapon_dice,
        range_m=eff.range,
        two_handed=eff.two_handed,
    )


def primary_stat_for_weapon(weapon: _Weapon) -> StatKey:
    """1.5m 이하 근접 → STR, 초과 → DEX."""
    return "STR" if weapon.range_m <= RULES.combat.unarmed.range_m else "DEX"


def enemy_defense(defender: Character, items: dict[str, Item]) -> int:
    """기준 10 + 4 슬롯 (head/top/bottom/feet) 의 ArmorEffect.defense 합."""
    total = 10
    for slot in _ARMOR_SLOTS:
        slot_id = getattr(defender.equipment, slot)
        if slot_id is None:
            continue
        item = items.get(slot_id)
        if item is None or item.effects is None:
            continue
        if isinstance(item.effects, ArmorEffect):
            total += item.effects.defense
    return total


# --- 명중·데미지 --------------------------------------------------------------


class AttackOutcome(BaseModel):
    """한 번의 공격 굴림 결과 — dual-wield 면 2 개가 발행된다."""
    hand: Literal["main", "off"]
    weapon_id: str | None
    primary_stat: StatKey
    nat_d20: int
    mod: int
    total: int
    required_roll: int
    grade: Grade
    damage: int


def _resolve_hands(attacker: Character, items: dict[str, Item]) -> list[tuple[Literal["main", "off"], _Weapon]]:
    """장비된 양손을 (hand, weapon) 시퀀스로. 양손 무기 한 자루 → 1 항목, dual-wield → 2 항목, 빈손 → unarmed 1 항목."""
    dom = attacker.dominant_hand  # "left" | "right"
    main_slot = "leftHand" if dom == "left" else "rightHand"
    off_slot = "rightHand" if dom == "left" else "leftHand"
    main_w = _weapon_for_slot(getattr(attacker.equipment, main_slot), items)
    off_w = _weapon_for_slot(getattr(attacker.equipment, off_slot), items)

    # 양손 무기는 한 슬롯에만 들고 있어도 두 슬롯 점거 — 명중도 한 번.
    if main_w is not None and main_w.two_handed:
        return [("main", main_w)]
    if off_w is not None and off_w.two_handed:
        return [("main", off_w)]

    if main_w is None and off_w is None:
        return [("main", _unarmed_weapon())]
    if main_w is not None and off_w is None:
        return [("main", main_w)]
    if main_w is None and off_w is not None:
        return [("main", off_w)]
    # dual-wield
    return [("main", main_w), ("off", off_w)]  # type: ignore[list-item]


def _damage_for_grade(weapon: _Weapon, mod: int, grade: Grade, hand: Literal["main", "off"], rng: random.Random) -> int:
    """grade·hand 별 데미지. 보조 손은 mod 없음, 크리는 다이스 두 번 + mod 한 번."""
    if grade in ("failure", "critical_failure"):
        return 0
    n, sides, bonus = _dice_count_and_sides(weapon.dice)
    base = sum(rng.randint(1, sides) for _ in range(n)) + bonus
    if grade == "critical_success":
        crit = sum(rng.randint(1, sides) for _ in range(n))
        base += crit
    if hand == "off":
        return max(0, base)  # 보조 손은 mod 안 더함
    return max(0, base + mod)


def attack(
    attacker: Character,
    defender: Character,
    items: dict[str, Item],
    rng: random.Random | None = None,
) -> list[AttackOutcome]:
    """한 차례의 공격 — 들고 있는 무기 구성에 따라 1~2 회 굴림."""
    r = rng or random
    defense = enemy_defense(defender, items)
    hands = _resolve_hands(attacker, items)
    outcomes: list[AttackOutcome] = []
    for hand, weapon in hands:
        stat_key = primary_stat_for_weapon(weapon)
        stat_value = getattr(attacker.stats, stat_key)
        mod = stat_modifier(stat_value)
        nat = r.randint(1, 20)
        total = nat + mod
        req = sigmoid_required_roll(defense, stat_value)
        grade = compute_grade(nat, total, req)
        damage = _damage_for_grade(weapon, mod, grade, hand, r)
        outcomes.append(
            AttackOutcome(
                hand=hand,
                weapon_id=weapon.item_id,
                primary_stat=stat_key,
                nat_d20=nat,
                mod=mod,
                total=total,
                required_roll=req,
                grade=grade,
                damage=damage,
            )
        )
    return outcomes


# --- 이니셔티브 ---------------------------------------------------------------


def roll_initiative(
    participants: list[Character],
    rng: random.Random | None = None,
) -> list[str]:
    """모든 참가자 d20 + DEX_mod 굴려 내림차순 정렬한 id 리스트.

    동률은 DEX 원값 → id 알파벳 순으로 안정적 tiebreak.
    """
    r = rng or random
    rolled: list[tuple[int, int, str]] = []
    for c in participants:
        roll = r.randint(1, 20) + stat_modifier(c.stats.DEX)
        rolled.append((roll, c.stats.DEX, c.id))
    rolled.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [t[2] for t in rolled]


# --- NPC AI -------------------------------------------------------------------


def _has_heal_skill(c: Character) -> bool:
    for s in (*c.racial_skills, *c.learned_skills):
        if s.type == "heal":
            return True
    return False


def _filter_alive_in_location(actor: Character, candidates: list[Character]) -> list[Character]:
    return [c for c in candidates if c.alive and c.id != actor.id and c.location_id == actor.location_id]


def pick_target(
    actor: Character,
    candidates: list[Character],
    rng: random.Random | None = None,
) -> Character | None:
    """combat_behavior 에 따라 한 명 선택. None 이면 폴백 (단순 랜덤).

    `nearest` 의 거리 metric: 같은 location 안에서 정밀 위치 모델이 없어 turn_order 인덱스가 아닌 후보 리스트 등장 순서를 그대로 "가까운 순" 으로 본다.
    `highest_threat` 는 P2 단계에선 nearest 폴백 — round-log 누적이 GameState 에 들어오는 P3 에서 정교화.
    """
    r = rng or random
    pool = _filter_alive_in_location(actor, candidates)
    if not pool:
        return None

    behavior = actor.combat_behavior
    if behavior is None or behavior.attack_priority is None:
        # 가중치 합산 모드. nearest = 첫 후보, random = 그 외.
        return _weighted_pick(pool, behavior, r)

    mode = behavior.attack_priority
    if mode == "nearest":
        return pool[0]
    if mode == "lowest_hp":
        return min(pool, key=lambda c: (c.hp, c.id))
    if mode == "random":
        return r.choice(pool)
    if mode == "healer_first":
        healers = [c for c in pool if _has_heal_skill(c)]
        if healers:
            return min(healers, key=lambda c: (c.hp, c.id))
        return min(pool, key=lambda c: (c.hp, c.id))
    if mode == "highest_threat":
        # P2: round-log 부재 — nearest 와 동일하게 폴백.
        return pool[0]
    return pool[0]


def _weighted_pick(
    pool: list[Character],
    behavior: CombatBehavior | None,
    rng: random.Random,
) -> Character:
    if behavior is None or len(pool) == 1:
        return pool[0]
    nw = max(0, behavior.nearest_weight)
    rw = max(0, behavior.random_weight)
    total = nw + rw
    if total == 0:
        return pool[0]
    pick = rng.randint(1, total)
    if pick <= nw:
        return pool[0]
    return rng.choice(pool)


# --- flee ---------------------------------------------------------------------


def should_attempt_flee(actor: Character, rng: random.Random | None = None) -> bool:
    """flee_hp_percent 임계 미만이면 `clamp((임계 - 현재HP%) * 2, 0, 100)` 확률로 시도."""
    behavior = actor.combat_behavior
    if behavior is None or behavior.flee_hp_percent is None:
        return False
    if actor.max_hp <= 0:
        return False
    hp_pct = (actor.hp / actor.max_hp) * 100
    if hp_pct >= behavior.flee_hp_percent:
        return False
    prob = max(0, min(100, (behavior.flee_hp_percent - hp_pct) * 2))
    r = rng or random
    return r.randint(1, 100) <= prob


def try_flee(actor: Character, rng: random.Random | None = None) -> tuple[bool, int]:
    """flee 굴림 한 번. 반환: (성공 여부, 굴림 합)."""
    f = RULES.combat.flee
    r = rng or random
    roll = roll_dice(f.dice, r)
    if f.dex_modifier:
        roll += stat_modifier(actor.stats.DEX)
    return (roll >= f.base_dc, roll)


# --- 라이프사이클 -------------------------------------------------------------


def start_combat(
    state: GameState,
    enemy_ids: list[str],
    rng: random.Random | None = None,
) -> CombatState:
    """combat_state 부팅. 참가자 = player + enemy_ids, 이니셔티브 굴려 정렬.

    state.combat_state 에 직접 박아 반환.
    """
    participants_ids = [state.player_id, *enemy_ids]
    participants = [state.characters[pid] for pid in participants_ids]
    order = roll_initiative(participants, rng=rng)
    cs = CombatState(
        turn_order=order,
        current_turn=0,
        round=1,
        surprise=None,
        enemy_ids=list(enemy_ids),
    )
    state.combat_state = cs
    return cs


def end_combat(state: GameState) -> None:
    state.combat_state = None


def current_actor_id(state: GameState) -> str | None:
    cs = state.combat_state
    if cs is None or not cs.turn_order:
        return None
    return cs.turn_order[cs.current_turn]


def advance_turn(state: GameState) -> None:
    """current_turn 다음 인덱스로. 한 바퀴 돌면 round +1."""
    cs = state.combat_state
    if cs is None or not cs.turn_order:
        return
    cs.current_turn += 1
    if cs.current_turn >= len(cs.turn_order):
        cs.current_turn = 0
        cs.round += 1


def remove_from_combat(state: GameState, actor_id: str) -> None:
    """actor_id 를 turn_order 에서 제거. 도주·사망 시 호출. enemy_ids 에서도 제거."""
    cs = state.combat_state
    if cs is None or actor_id not in cs.turn_order:
        return
    idx = cs.turn_order.index(actor_id)
    cs.turn_order.remove(actor_id)
    if actor_id in cs.enemy_ids:
        cs.enemy_ids.remove(actor_id)
    # current_turn 보정: 제거된 위치 이전이면 1 감소, 같으면 그 자리에서 다음 행위자가 들어옴.
    if idx < cs.current_turn:
        cs.current_turn -= 1
    if cs.turn_order and cs.current_turn >= len(cs.turn_order):
        cs.current_turn = 0
        cs.round += 1


def check_combat_end(state: GameState) -> Literal["victory", "defeat", "fled"] | None:
    """종료 조건 검사.

    - 적 측 (`enemy_ids`) 이 모두 dead/도주 → victory
    - player 가 dead → defeat
    - 적이 모두 도주 (사망이 아닌 turn_order 제거) → fled (P2: 도주만 따로 구분 안 하고 victory 와 동일하게 처리해도 무방하지만 docs 따라 보존)
    """
    cs = state.combat_state
    if cs is None:
        return None
    player = state.characters.get(state.player_id)
    if player is not None and not player.alive:
        return "defeat"

    enemies = [state.characters.get(eid) for eid in cs.enemy_ids]
    enemies_alive = [e for e in enemies if e is not None and e.alive]
    if not enemies_alive:
        # 적 전멸. 단 enemy_ids 에서 도주로 제거된 경우는 alive=True 이지만 enemy_ids 에 없음.
        return "victory"
    return None


# --- 데미지 적용 / 사망 처리 --------------------------------------------------


def apply_attack_to_defender(
    state: GameState,
    defender_id: str,
    damage: int,
    *,
    nat_d20: int | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """damage 만큼 hp 깎고 사망/death-save 분기.

    반환: `{hp_before, hp_after, downed: bool, dying: bool, dead: bool, revived: bool}`.
    `nat_d20` 이 1 (critical_failure 데미지) 일 때 death_save 도중이면 실패 +crit_inc.
    """
    defender = state.characters[defender_id]
    hp_before = defender.hp
    hp_after = max(0, defender.hp - damage)
    defender.hp = hp_after
    if dirty is not None:
        dirty.add(("characters", defender_id))

    out = {
        "hp_before": hp_before,
        "hp_after": hp_after,
        "downed": False,
        "dying": False,
        "dead": False,
        "revived": False,
    }

    # death-save 도중 추가 데미지: 실패 카운트 증가. 사망 임계 도달 시 즉시 사망.
    if defender.death_saves is not None:
        inc = (
            RULES.death.crit_damage_failure_inc
            if nat_d20 == 1
            else RULES.death.damage_failure_inc
        )
        defender.death_saves.failures = min(
            RULES.death.failures_to_die, defender.death_saves.failures + inc
        )
        if defender.death_saves.failures >= RULES.death.failures_to_die:
            _kill(defender)
            out["dead"] = True
        return out

    if hp_after > 0:
        return out

    # hp 0 으로 다운된 첫 순간.
    out["downed"] = True
    is_player = defender.is_player

    if is_player and defender.revive_coins > 0:
        defender.revive_coins -= 1
        defender.hp = max(1, round(defender.max_hp * RULES.death.revive_ratio))
        defender.death_saves = None
        out["revived"] = True
        out["hp_after"] = defender.hp
        return out

    if RULES.death.instant_death or not is_player:
        _kill(defender)
        out["dead"] = True
        return out

    # player 가 죽지 않고 죽어가는 중.
    defender.death_saves = DeathSaveState()
    out["dying"] = True
    return out


def _kill(defender: Character) -> None:
    defender.alive = False
    defender.hp = 0
    defender.death_saves = None


def tick_death_save(
    state: GameState,
    actor_id: str,
    *,
    rng: random.Random | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> tuple[Literal["progress", "stable", "dead"], int]:
    """death_save 1 회. 반환: (상태, d20 굴림값).

    - d20 ≥ save_dc → success +1
    - d20 < save_dc → failure +1
    - 성공 = successes_to_stabilize → stable (hp=auto_revive_hp, death_saves=None)
    - 실패 = failures_to_die → dead (alive=False)
    """
    actor = state.characters[actor_id]
    if actor.death_saves is None:
        actor.death_saves = DeathSaveState()
    r = rng or random
    roll = r.randint(1, 20)
    if roll >= RULES.death.save_dc:
        actor.death_saves.successes = min(
            RULES.death.successes_to_stabilize, actor.death_saves.successes + 1
        )
    else:
        actor.death_saves.failures = min(
            RULES.death.failures_to_die, actor.death_saves.failures + 1
        )
    if dirty is not None:
        dirty.add(("characters", actor_id))

    if actor.death_saves.successes >= RULES.death.successes_to_stabilize:
        actor.hp = RULES.death.auto_revive_hp
        actor.death_saves = None
        return ("stable", roll)
    if actor.death_saves.failures >= RULES.death.failures_to_die:
        _kill(actor)
        return ("dead", roll)
    return ("progress", roll)


# --- AI 후보 선택 헬퍼 --------------------------------------------------------


def pick_npc_target(
    state: GameState,
    actor_id: str,
    rng: random.Random | None = None,
) -> Character | None:
    """combat_state 안 actor 의 적 후보를 그러모아 pick_target 에 위임.

    적은 cs.enemy_ids 의 보수 — actor 가 enemy_ids 안이면 player 가 적, actor 가 player 면 enemy_ids 가 적.
    """
    cs = state.combat_state
    if cs is None:
        return None
    actor = state.characters[actor_id]
    if actor_id == state.player_id:
        candidates_ids = list(cs.enemy_ids)
    else:
        candidates_ids = [state.player_id]
    candidates = [state.characters[cid] for cid in candidates_ids if cid in state.characters]
    return pick_target(actor, candidates, rng=rng)
