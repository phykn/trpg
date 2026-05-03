"""Skill cast pipeline: gate → MP → range → AoE auto-target → grade adjustment → damage/heal/buff. Plus build_skill_from_candidate for LLM-recommended learn candidates."""

from __future__ import annotations

import hashlib
import random
import re

from ..domain.entities import ActiveBuff, Character, Skill, SkillCandidate
from ..domain.types import Grade
from ..domain.errors import SkillInvalid
from ..rules import RULES
from ..domain.state import GameState
from .combat import apply_attack_to_defender, enemy_defense, stat_modifier
from ..rules.dc import compute_grade, compute_required_roll

CastTargets = list[str]


def find_skill(actor: Character, skill_id: str, state: GameState) -> Skill:
    if skill_id not in actor.known_skill_ids:
        raise SkillInvalid(f"actor has no such skill: {skill_id}")
    skill = state.skills.get(skill_id)
    if skill is None:
        raise SkillInvalid(f"skill_id {skill_id!r} not in skills pool")
    return skill


def _validate_gate(actor: Character, skill: Skill) -> None:
    if actor.level < skill.level:
        raise SkillInvalid(f"level too low: actor={actor.level} < skill={skill.level}")
    if actor.mp < skill.mp_cost:
        raise SkillInvalid(f"not enough mp: {actor.mp} < {skill.mp_cost}")


def _resolve_targets(
    actor: Character,
    skill: Skill,
    state: GameState,
    requested: CastTargets,
) -> list[Character]:
    """Return target characters by target kind. AoE auto-expands."""
    if skill.target == "self":
        return [actor]

    if skill.target == "single":
        if len(requested) != 1:
            raise SkillInvalid(
                f"single-target skill needs 1 target, got {len(requested)}"
            )
        tid = requested[0]
        if tid not in state.characters:
            raise SkillInvalid(f"unknown target: {tid}")
        target = state.characters[tid]
        # Dead targets break the alive=False/hp>0 invariant if heal/buff lands on them,
        # and route into _kill again for attack skills. Treat as invalid up front.
        if not target.alive:
            raise SkillInvalid(f"target {tid} is incapacitated")
        return [target]

    # area: every living character in the same location (excluding the actor).
    if actor.location_id is None:
        raise SkillInvalid("area skill requires actor location")
    return [
        c
        for c in state.characters.values()
        if c.id != actor.id and c.alive and c.location_id == actor.location_id
    ]


def _validate_range(actor: Character, skill: Skill, targets: list[Character]) -> None:
    for t in targets:
        if t.id == actor.id:
            continue
        if t.location_id != actor.location_id:
            raise SkillInvalid(f"target {t.id} out of range (different location)")


def _grade_multiplier(grade: Grade | None) -> float:
    if grade is None:
        return 1.0
    return RULES.skill.grade_multipliers[grade]


def _skill_output(skill: Skill, mod: int, multiplier: float) -> int:
    return max(0, round(max(0, skill.power + mod) * multiplier))


def _apply_attack(
    skill: Skill,
    mod: int,
    target: Character,
    multiplier: float,
    state: GameState,
    dirty: set[tuple[str, str]] | None,
    attacker_id: str | None = None,
) -> dict:
    """Route skill damage through the same death-save / revive-coin pipeline
    as melee attacks. Returns the apply_attack_to_defender result with the
    computed `damage` merged in."""
    damage = _skill_output(skill, mod, multiplier)
    out = apply_attack_to_defender(
        state, target.id, damage, dirty=dirty, attacker_id=attacker_id
    )
    out["damage"] = damage
    return out


def _apply_heal(skill: Skill, mod: int, target: Character, multiplier: float) -> int:
    healed = _skill_output(skill, mod, multiplier)
    new_hp = min(target.max_hp, target.hp + healed)
    actual = new_hp - target.hp
    target.hp = new_hp
    return actual


def _apply_buff(skill: Skill, target: Character) -> ActiveBuff:
    description = skill.special_effect or skill.description or skill.name
    buff = ActiveBuff(description=description, duration=skill.duration)
    target.active_buffs.append(buff)
    return buff


def compute_cast_grade(
    actor: Character,
    skill: Skill,
    state: GameState,
    targets: CastTargets,
    *,
    rng: random.Random | None = None,
) -> tuple[Grade, int, int]:
    """attack/debuff skills resolve grade via a d20 roll. heal/buff/self are auto-success.

    Returns (grade, nat_d20, required_roll). Non-attack/debuff returns (success, 0, 0).
    attack: against target.defense. debuff: against target.WIS resistance (10 + WIS_mod).
    """
    if skill.type not in ("attack", "debuff") or not targets:
        return ("success", 0, 0)
    target_id = targets[0]
    target = state.characters.get(target_id)
    if target is None:
        return ("success", 0, 0)
    r = rng or random
    stat_value = getattr(actor.stats, skill.primary_stat)
    if skill.type == "attack":
        defense = enemy_defense(target, state.items)
    else:
        defense = 10 + stat_modifier(target.stats.WIS)
    nat = r.randint(1, 20)
    mod = stat_modifier(stat_value)
    total = nat + mod
    required = compute_required_roll(defense, stat_value)
    grade = compute_grade(nat, total, required)
    return (grade, nat, required)


def cast(
    actor: Character,
    skill_id: str,
    state: GameState,
    requested_targets: CastTargets,
    *,
    grade: Grade | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """Cast skill_id. On validation pass, apply effects and return a result dict.

    grade=None falls back to multiplier 1.0; in practice every call site goes through the combat branch so a real grade is always supplied.
    """
    skill = find_skill(actor, skill_id, state)
    _validate_gate(actor, skill)
    targets = _resolve_targets(actor, skill, state, requested_targets)
    _validate_range(actor, skill, targets)

    mod = stat_modifier(getattr(actor.stats, skill.primary_stat))
    multiplier = _grade_multiplier(grade)

    effects: list[dict] = []
    for t in targets:
        per: dict = {"target": t.id, "kind": skill.type}
        if skill.type == "attack":
            atk = _apply_attack(
                skill, mod, t, multiplier, state, dirty, attacker_id=actor.id
            )
            per["damage"] = atk["damage"]
            if atk.get("dead"):
                per["dead"] = True
            elif atk.get("dying"):
                per["dying"] = True
            elif atk.get("revived"):
                per["revived"] = True
        elif skill.type == "heal":
            per["healed"] = _apply_heal(skill, mod, t, multiplier)
            if dirty is not None:
                dirty.add(("characters", t.id))
        elif skill.type in ("buff", "debuff"):
            buff = _apply_buff(skill, t)
            per["buff"] = {
                "description": buff.description,
                "duration": buff.duration,
            }
            if dirty is not None:
                dirty.add(("characters", t.id))
        effects.append(per)

    actor.mp -= skill.mp_cost
    if dirty is not None:
        dirty.add(("characters", actor.id))

    return {
        "skill_id": skill.id,
        "skill_name": skill.name,
        "actor": actor.id,
        "mp_cost": skill.mp_cost,
        "multiplier": multiplier,
        "effects": effects,
    }


def tick_active_buffs(
    character: Character,
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> int:
    """Called at each turn end. duration -1; remove on 0. Returns the count of removed buffs."""
    if not character.active_buffs:
        return 0
    before = len(character.active_buffs)
    for b in character.active_buffs:
        b.duration -= 1
    character.active_buffs = [b for b in character.active_buffs if b.duration > 0]
    removed = before - len(character.active_buffs)
    if removed > 0 and dirty is not None:
        dirty.add(("characters", character.id))
    return removed


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Stable id from a (possibly non-ASCII) name. Non-ASCII falls back to a hash so distinct names stay distinct."""
    ascii_only = "".join(ch for ch in name if ord(ch) < 128)
    base = _SLUG_RE.sub("_", ascii_only.lower()).strip("_")
    if base:
        return base
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"skill_{digest}"


def _unique_skill_id(base: str, existing_ids: set[str]) -> str:
    sid = base
    n = 1
    while sid in existing_ids:
        n += 1
        sid = f"{base}_{n}"
    return sid


def _template_for(skill_type: str, level: int) -> dict:
    safe_level = max(0, level)
    if skill_type == "attack":
        return {
            "power": 5 + safe_level * 2,
            "mp_cost": 3 + safe_level,
            "range": 5.0,
            "duration": 0,
        }
    if skill_type == "heal":
        return {
            "power": 4 + safe_level * 2,
            "mp_cost": 4 + safe_level,
            "range": 5.0,
            "duration": 0,
        }
    return {
        "power": 0,
        "mp_cost": 2 + safe_level,
        "range": 5.0,
        "duration": 3,
    }


def build_skill_from_candidate(
    candidate: SkillCandidate,
    level: int,
    existing_ids: set[str],
) -> Skill:
    """LLM-produced candidate + level → Skill object. Engine-side numerics come from _template_for."""
    base = _slugify(candidate.name)
    sid = _unique_skill_id(f"{base}_l{level}", existing_ids)
    template = _template_for(candidate.type, level)
    return Skill(
        id=sid,
        name=candidate.name,
        description=candidate.description,
        type=candidate.type,
        target=candidate.target,
        primary_stat=candidate.primary_stat,
        special_effect=candidate.special_effect,
        level=level,
        power=template["power"],
        mp_cost=template["mp_cost"],
        range=template["range"],
        duration=template["duration"],
    )


def existing_skill_ids(state: GameState) -> set[str]:
    """For collision avoidance — every skill id currently in the pool."""
    return set(state.skills.keys())
