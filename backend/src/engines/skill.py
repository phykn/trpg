"""Skill cast — level/MP/range validation + effect application (P3 §2.6).

Cast pipeline (S1, core): level gate → MP check → range check → AoE auto-target →
grade adjustment → damage/heal/buff. S2: judge semantic matching. §2.3 step 4: LLM
learn-candidate recommendation (build_skill_from_candidate).

Damage/heal base: `power + primary_stat_modifier`. grade_multipliers tunes per stage.
Exact coefficients are a tuning knob — see `rules.skill.grade_multipliers`.
"""
from __future__ import annotations

import random
import re
from typing import Literal

from ..domain.entities import ActiveBuff, Character, Skill
from ..domain.types import Grade
from ..domain.errors import SkillInvalid
from ..agents.skill_recommend import SkillCandidate
from ..rules import RULES
from ..domain.state import GameState
from .combat import enemy_defense, stat_modifier
from ..rules.dc import compute_grade, sigmoid_required_roll

CastTargets = list[str]


def _all_skills(actor: Character) -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    for s in actor.racial_skills:
        out[s.id] = s
    for s in actor.learned_skills:
        out[s.id] = s
    return out


def find_skill(actor: Character, skill_id: str) -> Skill:
    skills = _all_skills(actor)
    if skill_id not in skills:
        raise SkillInvalid(f"actor has no such skill: {skill_id}")
    return skills[skill_id]


def _validate_gate(actor: Character, skill: Skill) -> None:
    if actor.level < skill.level:
        raise SkillInvalid(
            f"level too low: actor={actor.level} < skill={skill.level}"
        )
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
            raise SkillInvalid(f"single-target skill needs 1 target, got {len(requested)}")
        tid = requested[0]
        if tid not in state.characters:
            raise SkillInvalid(f"unknown target: {tid}")
        return [state.characters[tid]]

    # area: every living character in the same location (excluding the actor).
    if actor.location_id is None:
        raise SkillInvalid("area skill requires actor location")
    return [
        c
        for c in state.characters.values()
        if c.id != actor.id and c.alive and c.location_id == actor.location_id
    ]


def _validate_range(actor: Character, skill: Skill, targets: list[Character]) -> None:
    """Current rule — targets in other locations are out of range; same-location targets always pass."""
    for t in targets:
        if t.id == actor.id:
            continue
        if t.location_id != actor.location_id:
            raise SkillInvalid(
                f"target {t.id} out of range (different location)"
            )


def _grade_multiplier(grade: Grade | None) -> float:
    if grade is None:
        return 1.0
    return RULES.skill.grade_multipliers.get(grade, 1.0)


def _apply_attack(
    skill: Skill, mod: int, target: Character, multiplier: float
) -> int:
    base = max(0, skill.power + mod)
    damage = max(0, round(base * multiplier))
    target.hp = max(0, target.hp - damage)
    if target.hp == 0:
        target.alive = False
    return damage


def _apply_heal(
    skill: Skill, mod: int, target: Character, multiplier: float
) -> int:
    base = max(0, skill.power + mod)
    healed = max(0, round(base * multiplier))
    new_hp = min(target.max_hp, target.hp + healed)
    actual = new_hp - target.hp
    target.hp = new_hp
    return actual


def _apply_buff(
    skill: Skill, target: Character
) -> ActiveBuff:
    description = skill.special_effect or skill.description or skill.name
    buff = ActiveBuff(description=description, duration=skill.duration)
    target.active_buffs.append(buff)
    return buff


CastEffectKind = Literal["attack", "heal", "buff", "debuff"]


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
    required = sigmoid_required_roll(defense, stat_value)
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

    grade=None → out-of-combat cast (multiplier 1.0). Once judge integration runs, the grade is supplied and used for adjustment.
    """
    from .quest import check_quests  # deferred import — keeps engines/skill below engines/quest

    skill = find_skill(actor, skill_id)
    _validate_gate(actor, skill)
    targets = _resolve_targets(actor, skill, state, requested_targets)
    _validate_range(actor, skill, targets)

    mod = stat_modifier(getattr(actor.stats, skill.primary_stat))
    multiplier = _grade_multiplier(grade)

    effects: list[dict] = []
    killed_ids: list[str] = []
    for t in targets:
        per: dict = {"target": t.id, "kind": skill.type}
        if skill.type == "attack":
            per["damage"] = _apply_attack(skill, mod, t, multiplier)
            if not t.alive:
                per["dead"] = True
                killed_ids.append(t.id)
        elif skill.type == "heal":
            per["healed"] = _apply_heal(skill, mod, t, multiplier)
        elif skill.type in ("buff", "debuff"):
            buff = _apply_buff(skill, t)
            per["buff"] = {
                "description": buff.description,
                "duration": buff.duration,
            }
        effects.append(per)
        if dirty is not None:
            dirty.add(("characters", t.id))

    actor.mp -= skill.mp_cost
    if dirty is not None:
        dirty.add(("characters", actor.id))

    for victim_id in killed_ids:
        check_quests(state, "character_death", victim_id, dirty)

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
    surviving: list[ActiveBuff] = []
    removed = 0
    for b in character.active_buffs:
        new_d = b.duration - 1
        if new_d > 0:
            surviving.append(ActiveBuff(description=b.description, duration=new_d))
        else:
            removed += 1
    character.active_buffs = surviving
    if removed > 0 and dirty is not None:
        dirty.add(("characters", character.id))
    return removed


# --- Learn candidates (§2.3 step 4) ------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Non-ASCII names cannot be meaningfully transliterated, so fall back to 'skill'."""
    ascii_only = "".join(ch for ch in name if ord(ch) < 128)
    base = _SLUG_RE.sub("_", ascii_only.lower()).strip("_")
    return base or "skill"


def _unique_skill_id(base: str, existing_ids: set[str]) -> str:
    sid = base
    n = 1
    while sid in existing_ids:
        n += 1
        sid = f"{base}_{n}"
    return sid


def _template_for(skill_type: str, level: int) -> dict:
    """Numeric template by type and level. Exact coefficients are a P3 tuning knob."""
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
    # buff / debuff
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
    """For collision avoidance — collect every existing character's racial + learned skill ids."""
    ids: set[str] = set()
    for c in state.characters.values():
        for s in c.racial_skills:
            ids.add(s.id)
        for s in c.learned_skills:
            ids.add(s.id)
    return ids
