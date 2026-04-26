"""스킬 cast — level/MP/사정거리 검증 + 효과 적용 (P3 §2.6).

cast 파이프라인 (S1, 핵심): level 게이트 → MP 검증 → 사정거리 검증 → AoE 대상 자동 →
grade 보정 → 데미지/회복/버프 적용. judge 의 의미 매칭 / racial_skills 자동 발동 /
LLM 학습 후보 (§2.3 4단계) 는 후속.

데미지·회복 베이스: `power + primary_stat_modifier`. grade_multipliers 로 stage 별 보정.
정확한 계수는 튜닝 노브 — `rules.skill.grade_multipliers` 에서.
"""
from __future__ import annotations

from typing import Literal

from ..domain.entities import ActiveBuff, Character, Skill
from ..domain.types import Grade
from ..errors import SkillInvalid
from ..rules import RULES
from ..state.models import GameState
from .combat import stat_modifier

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
    """target 종류별 대상 캐릭터 리스트 반환. AoE 면 자동 확장."""
    if skill.target == "self":
        return [actor]

    if skill.target == "single":
        if len(requested) != 1:
            raise SkillInvalid(f"single-target skill needs 1 target, got {len(requested)}")
        tid = requested[0]
        if tid not in state.characters:
            raise SkillInvalid(f"unknown target: {tid}")
        return [state.characters[tid]]

    # area: 같은 location 의 살아있는 캐릭터 전원 (자기 자신 제외).
    if actor.location_id is None:
        raise SkillInvalid("area skill requires actor location")
    return [
        c
        for c in state.characters.values()
        if c.id != actor.id and c.alive and c.location_id == actor.location_id
    ]


def _validate_range(actor: Character, skill: Skill, targets: list[Character]) -> None:
    """현재 룰 — 다른 location 의 대상은 사거리 밖. 같은 location 안에서는 사거리 통과."""
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


def cast(
    actor: Character,
    skill_id: str,
    state: GameState,
    requested_targets: CastTargets,
    *,
    grade: Grade | None = None,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """skill_id 를 cast. 검증 통과 시 효과 적용, 결과 dict 반환.

    grade=None → 평시 cast (multiplier 1.0). judge 통합 시 grade 가 들어와 보정 적용.
    """
    skill = find_skill(actor, skill_id)
    _validate_gate(actor, skill)
    targets = _resolve_targets(actor, skill, state, requested_targets)
    _validate_range(actor, skill, targets)

    mod = stat_modifier(getattr(actor.stats, skill.primary_stat))
    multiplier = _grade_multiplier(grade)

    effects: list[dict] = []
    for t in targets:
        per: dict = {"target": t.id, "kind": skill.type}
        if skill.type == "attack":
            per["damage"] = _apply_attack(skill, mod, t, multiplier)
            if not t.alive:
                per["dead"] = True
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
    """매 턴 종료 시 호출. duration -1, 0 이 되면 제거. 제거된 버프 수 반환."""
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
