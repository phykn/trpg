"""Combat engine core — pure rules, no LLM calls.

The caller (pipeline/turn.py) drives round progression; this module exposes deterministic units like a single attack roll, damage, AI decision, or flee attempt.
Spec source: docs/03-features.md §1.1-§1.6.
"""
from __future__ import annotations

import random
import re
from typing import Literal

from pydantic import BaseModel

from ..domain.entities import (
    ARMOR_SLOTS,
    ArmorEffect,
    Character,
    CombatBehavior,
    DeathSaveState,
    Item,
    Skill,
    WeaponEffect,
)
from ..domain.types import Grade, StatKey
from ..rules import RULES
from ..domain.state import CombatState, GameState
from ..rules.dc import compute_grade, sigmoid_required_roll


# --- Common ------------------------------------------------------------------


DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")


def stat_modifier(stat_value: int) -> int:
    """D&D 5e: floor((stat - 10) / 2). 10 → 0, 0 → -5, 20 → +5."""
    return (stat_value - 10) // 2


def _parse_dice(spec: str) -> tuple[int, int, int]:
    """`1d8`, `2d6+3`, `1d4-1` → (n, sides, bonus)."""
    m = DICE_RE.match(spec)
    if not m:
        raise ValueError(f"invalid dice spec: {spec!r}")
    n, sides = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    return n, sides, bonus


def roll_dice(spec: str, rng: random.Random | None = None) -> int:
    """Roll the spec and return the sum."""
    n, sides, bonus = _parse_dice(spec)
    r = rng or random
    return sum(r.randint(1, sides) for _ in range(n)) + bonus


# --- Weapon / defense projection ---------------------------------------------


class _Weapon(BaseModel):
    """Weapon projection for one attack roll — a real Item or the unarmed fallback."""
    item_id: str | None  # None = unarmed
    dice: str
    range_m: float
    two_handed: bool


def _unarmed_weapon() -> _Weapon:
    u = RULES.combat.unarmed
    return _Weapon(item_id=None, dice=u.damage, range_m=u.range_m, two_handed=False)


def _weapon_for_slot(slot_id: str | None, items: dict[str, Item]) -> _Weapon | None:
    """Equipment slot → weapon projection. None if empty or non-weapon."""
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
    """Melee within 1.5 m → STR, beyond → DEX."""
    return "STR" if weapon.range_m <= RULES.combat.unarmed.range_m else "DEX"


def enemy_defense(defender: Character, items: dict[str, Item]) -> int:
    """Base 10 + sum of ArmorEffect.defense across the 4 slots (head/top/bottom/feet)."""
    total = 10
    for slot in ARMOR_SLOTS:
        slot_id = getattr(defender.equipment, slot)
        if slot_id is None:
            continue
        item = items.get(slot_id)
        if item is None or item.effects is None:
            continue
        if isinstance(item.effects, ArmorEffect):
            total += item.effects.defense
    return total


# --- Hit / damage ------------------------------------------------------------


class AttackOutcome(BaseModel):
    """Result of one attack roll — dual-wield emits two of these."""
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
    """Equipped hands as a (hand, weapon) sequence. Two-handed weapon → 1 item, dual-wield → 2, empty hands → unarmed 1 item."""
    dom = attacker.dominant_hand  # "left" | "right"
    main_slot = "leftHand" if dom == "left" else "rightHand"
    off_slot = "rightHand" if dom == "left" else "leftHand"
    main_w = _weapon_for_slot(getattr(attacker.equipment, main_slot), items)
    off_w = _weapon_for_slot(getattr(attacker.equipment, off_slot), items)

    # A two-handed weapon held in one slot still occupies both slots — only one attack roll.
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
    """Damage by grade and hand. Off-hand gets no mod; crit rolls dice twice but adds mod once."""
    if grade in ("failure", "critical_failure"):
        return 0
    n, sides, bonus = _parse_dice(weapon.dice)
    base = sum(rng.randint(1, sides) for _ in range(n)) + bonus
    if grade == "critical_success":
        crit = sum(rng.randint(1, sides) for _ in range(n))
        base += crit
    if hand == "off":
        return max(0, base)  # off-hand does not add mod
    return max(0, base + mod)


def attack(
    attacker: Character,
    defender: Character,
    items: dict[str, Item],
    rng: random.Random | None = None,
) -> list[AttackOutcome]:
    """One attack action — 1 or 2 rolls depending on weapon configuration."""
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


# --- Initiative --------------------------------------------------------------


def roll_initiative(
    participants: list[Character],
    rng: random.Random | None = None,
) -> list[str]:
    """List of ids sorted descending by d20 + DEX_mod across all participants.

    Ties are broken stably by raw DEX → id alphabetical.
    """
    r = rng or random
    rolled: list[tuple[int, int, str]] = []
    for c in participants:
        roll = r.randint(1, 20) + stat_modifier(c.stats.DEX)
        rolled.append((roll, c.stats.DEX, c.id))
    rolled.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [t[2] for t in rolled]


# --- NPC AI -------------------------------------------------------------------


def _has_heal_skill(c: Character, skills_pool: dict[str, Skill]) -> bool:
    for sid in (*c.racial_skill_ids, *c.learned_skill_ids):
        s = skills_pool.get(sid)
        if s is not None and s.type == "heal":
            return True
    return False


def _filter_alive_in_location(actor: Character, candidates: list[Character]) -> list[Character]:
    return [c for c in candidates if c.alive and c.id != actor.id and c.location_id == actor.location_id]


def pick_target(
    actor: Character,
    candidates: list[Character],
    skills_pool: dict[str, Skill] | None = None,
    rng: random.Random | None = None,
    damage_dealt: dict[str, int] | None = None,
) -> Character | None:
    """Pick one target according to combat_behavior. Falls back to a simple random pick when None.

    `nearest` distance metric: there is no fine-grained position model within a location, so we treat the candidate list's appearance order (not turn_order index) as "nearest first".
    `highest_threat` reads combat_state.damage_dealt and targets the enemy that has dealt the most damage (falls back to nearest if there is no record).
    """
    r = rng or random
    pool = _filter_alive_in_location(actor, candidates)
    if not pool:
        return None

    behavior = actor.combat_behavior
    if behavior is None or behavior.attack_priority is None:
        # Weighted-sum mode. nearest = first candidate, random = anything else.
        if behavior is None or len(pool) == 1:
            return pool[0]
        nw = max(0, behavior.nearest_weight)
        rw = max(0, behavior.random_weight)
        total = nw + rw
        if total == 0:
            return pool[0]
        if r.randint(1, total) <= nw:
            return pool[0]
        return r.choice(pool)

    mode = behavior.attack_priority
    if mode == "nearest":
        return pool[0]
    if mode == "lowest_hp":
        return min(pool, key=lambda c: (c.hp, c.id))
    if mode == "random":
        return r.choice(pool)
    if mode == "healer_first":
        skill_pool = skills_pool or {}
        healers = [c for c in pool if _has_heal_skill(c, skill_pool)]
        if healers:
            return min(healers, key=lambda c: (c.hp, c.id))
        return min(pool, key=lambda c: (c.hp, c.id))
    if mode == "highest_threat":
        if damage_dealt:
            scored = [(damage_dealt.get(c.id, 0), c) for c in pool]
            best = max(scored, key=lambda t: (t[0], -t[1].hp))
            if best[0] > 0:
                return best[1]
        return pool[0]
    return pool[0]


# --- flee ---------------------------------------------------------------------


def should_attempt_flee(actor: Character, rng: random.Random | None = None) -> bool:
    """Below the flee_hp_percent threshold, try with probability `clamp((threshold - current HP%) * 2, 0, 100)`."""
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
    """One flee roll. Returns (success, roll total)."""
    f = RULES.combat.flee
    r = rng or random
    roll = roll_dice(f.dice, r)
    if f.dex_modifier:
        roll += stat_modifier(actor.stats.DEX)
    return (roll >= f.base_dc, roll)


# --- Lifecycle ---------------------------------------------------------------


def start_combat(
    state: GameState,
    enemy_ids: list[str],
    rng: random.Random | None = None,
    surprise: Literal["player", "enemy"] | None = None,
) -> CombatState:
    """Boot combat_state. Participants = player + companions on both sides + enemy_ids, sorted by initiative.

    Stamps the result directly onto state.combat_state. surprise='enemy' means the player
    cannot act in the first round (e.g. ambush during sleep). Companions auto-join with
    their patron (§2.9).
    """
    raw: list[str] = [state.player_id]
    if state.player_id in state.characters:
        raw.extend(state.characters[state.player_id].companions)
    for eid in enemy_ids:
        raw.append(eid)
        if eid in state.characters:
            raw.extend(state.characters[eid].companions)
    unique = [cid for cid in dict.fromkeys(raw) if cid in state.characters]
    participants = [state.characters[pid] for pid in unique]
    order = roll_initiative(participants, rng=rng)
    cs = CombatState(
        turn_order=order,
        current_turn=0,
        round=1,
        surprise=surprise,
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
    """Advance current_turn to the next index. Round increments after a full loop."""
    cs = state.combat_state
    if cs is None or not cs.turn_order:
        return
    cs.current_turn += 1
    if cs.current_turn >= len(cs.turn_order):
        cs.current_turn = 0
        cs.round += 1


def remove_from_combat(state: GameState, actor_id: str) -> None:
    """Remove actor_id from turn_order. Called on flee/death. Also removed from enemy_ids."""
    cs = state.combat_state
    if cs is None or actor_id not in cs.turn_order:
        return
    idx = cs.turn_order.index(actor_id)
    cs.turn_order.remove(actor_id)
    if actor_id in cs.enemy_ids:
        cs.enemy_ids.remove(actor_id)
    # current_turn adjustment: if the removed slot was earlier, decrement by 1; if equal, the next actor steps into the same slot.
    if idx < cs.current_turn:
        cs.current_turn -= 1
    if cs.turn_order and cs.current_turn >= len(cs.turn_order):
        cs.current_turn = 0
        cs.round += 1


def check_combat_end(state: GameState) -> Literal["victory", "defeat"] | None:
    """Check end conditions — enemies wiped/fled = victory, player dead = defeat.

    Fleeing removes the enemy from enemy_ids, so an empty enemies_alive list resolves to victory.
    flow/combat_phase yields a separate "fled" outcome, so we do not distinguish it here.
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
        # Enemies wiped out. Note: actors removed from enemy_ids via flee are alive=True but no longer in enemy_ids.
        return "victory"
    return None


# --- Damage application / death handling -------------------------------------


def apply_attack_to_defender(
    state: GameState,
    defender_id: str,
    damage: int,
    *,
    nat_d20: int | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """Subtract damage from hp and route to death / death-save branches.

    Returns: `{hp_before, hp_after, downed: bool, dying: bool, dead: bool, revived: bool}`.
    When `nat_d20` is 1 (critical_failure damage) during a death save, failures += crit_inc.
    On death, the quest character_death trigger is evaluated.
    """
    from .quest import check_quests  # deferred import — avoid cycle within pipeline layer
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

    # Extra damage while in death-save: bump failure count. Hitting the death threshold kills immediately.
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
            check_quests(state, "character_death", defender_id, dirty)
        return out

    if hp_after > 0:
        return out

    # First moment of being downed at hp 0.
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
        check_quests(state, "character_death", defender_id, dirty)
        return out

    # Player not dead yet — dying state.
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
    d20: int | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> tuple[Literal["progress", "stable", "dead"], int]:
    """One death_save tick. Returns (status, d20 roll).

    - d20 ≥ save_dc → success +1
    - d20 < save_dc → failure +1
    - successes = successes_to_stabilize → stable (hp=auto_revive_hp, death_saves=None)
    - failures = failures_to_die → dead (alive=False)

    `d20` lets the caller pass an externally-rolled value (used by /roll
    when the player triggered the dice button). Otherwise we roll internally.
    """
    actor = state.characters[actor_id]
    if actor.death_saves is None:
        actor.death_saves = DeathSaveState()
    if d20 is not None:
        roll = d20
    else:
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


# --- AI candidate selection helpers ------------------------------------------


def pick_npc_target(
    state: GameState,
    actor_id: str,
    rng: random.Random | None = None,
) -> Character | None:
    """Collect the actor's enemy candidates by faction within combat_state and delegate to pick_target.

    Companions of the same patron are allies (§2.9). If the actor is on the player side
    (player or player.companions), the enemy side is the targets; otherwise the player side is.
    """
    cs = state.combat_state
    if cs is None:
        return None
    actor = state.characters[actor_id]

    player_side: set[str] = {state.player_id}
    if state.player_id in state.characters:
        player_side.update(state.characters[state.player_id].companions)

    enemy_side: set[str] = set(cs.enemy_ids)
    for eid in cs.enemy_ids:
        if eid in state.characters:
            enemy_side.update(state.characters[eid].companions)

    targets_ids = enemy_side if actor_id in player_side else player_side
    candidates = [
        state.characters[cid] for cid in targets_ids if cid in state.characters
    ]
    return pick_target(
        actor, candidates, state.skills, rng=rng, damage_dealt=cs.damage_dealt
    )


def record_damage(state: GameState, attacker_id: str, damage: int) -> None:
    """Accumulate into combat_state.damage_dealt. Read by highest_threat AI."""
    cs = state.combat_state
    if cs is None or damage <= 0:
        return
    cs.damage_dealt[attacker_id] = cs.damage_dealt.get(attacker_id, 0) + damage
