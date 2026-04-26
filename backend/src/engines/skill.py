"""스킬 cast — level/MP/사정거리 검증 + 효과 적용 (P3 §2.6).

cast 파이프라인 (S1, 핵심): level 게이트 → MP 검증 → 사정거리 검증 → AoE 대상 자동 →
grade 보정 → 데미지/회복/버프 적용. S2: judge 의미 매칭. §2.3 4단계: LLM 학습 후보
추천 (build_skill_from_candidate).

데미지·회복 베이스: `power + primary_stat_modifier`. grade_multipliers 로 stage 별 보정.
정확한 계수는 튜닝 노브 — `rules.skill.grade_multipliers` 에서.
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


def compute_cast_grade(
    actor: Character,
    skill: Skill,
    state: GameState,
    targets: CastTargets,
    *,
    rng: random.Random | None = None,
) -> tuple[Grade, int, int]:
    """attack/debuff 스킬은 d20 굴림으로 grade 결정. heal/buff/self 는 success.

    반환: (grade, nat_d20, required_roll). 비-attack/debuff 면 (success, 0, 0).
    attack: target.defense 기준. debuff: target.WIS 저항 (10 + WIS_mod).
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


# --- 학습 후보 (§2.3 4단계) ----------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_HANGUL_TO_LATIN_PLACEHOLDER = "skill"


def _slugify(name: str) -> str:
    """한글 이름은 유의미한 ASCII 변환이 어려우니 placeholder. 영어가 섞여 있으면 그것만 추출."""
    ascii_only = "".join(ch for ch in name if ord(ch) < 128)
    base = _SLUG_RE.sub("_", ascii_only.lower()).strip("_")
    return base or _HANGUL_TO_LATIN_PLACEHOLDER


def _unique_skill_id(base: str, existing_ids: set[str]) -> str:
    sid = base
    n = 1
    while sid in existing_ids:
        n += 1
        sid = f"{base}_{n}"
    return sid


def _template_for(skill_type: str, level: int) -> dict:
    """type/level 기준 수치 템플릿. 정확한 계수는 P3 후속 튜닝."""
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
    """LLM 산출 candidate + level → Skill 객체. 엔진 측 수치는 _template_for 가 채움."""
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
    """충돌 회피용 — 기존 모든 character 의 racial+learned skill id 모음."""
    ids: set[str] = set()
    for c in state.characters.values():
        for s in c.racial_skills:
            ids.add(s.id)
        for s in c.learned_skills:
            ids.add(s.id)
    return ids
