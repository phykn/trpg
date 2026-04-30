"""Build pipeline — orchestrates decompose → skeleton entity writes → attach
patch pass → meta files → invariant sweep, turning one prose .md into a
complete scenario directory.

Decomposition machinery (Phase A/B/C models, validation, LLM calls) lives in
`decompose.py`; this module is the orchestrator and its helpers.
"""

import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from src.domain.entities import (
    ArmorEffect,
    Character,
    Connection,
    Item,
    WeaponEffect,
)
from src.engines.invariants import Scenario, check_scenario
from src.llm import LLMClient

from .decompose import Decomposition, decompose_prose
from .runner import (
    EntityWriterError,
    write_entity,
    write_entity_to_disk,
)


# --- pipeline helpers ------------------------------------------------------

def _hint_with_id(forced_id: str, role: str, extra: str = "") -> str:
    base = f"id 를 정확히 '{forced_id}' 로 박을 것. 역할: {role}."
    return f"{base} {extra}".strip()


async def _write_step(
    *,
    kind: str,
    forced_id: str,
    hint: str,
    scenario_dir: Path,
    agents_dir: Path,
    llm: LLMClient,
    extra_check: Callable[[BaseModel], None] | None = None,
    think: bool = True,
    run_dir: Path | None = None,
    critic_prompt_path: Path | None = None,
    decomp_summary: str = "",
    skeleton: bool = False,
) -> BaseModel:
    entity, msgs = await write_entity(
        kind=kind,
        scenario_dir=scenario_dir,
        agents_dir=agents_dir,
        hint=hint,
        llm=llm,
        force_id=forced_id,
        extra_check=extra_check,
        think=think,
        critic_prompt_path=critic_prompt_path,
        decomp_summary=decomp_summary,
        skeleton=skeleton,
    )
    write_entity_to_disk(entity, scenario_dir, kind)
    if run_dir is not None:
        msg_path = run_dir / f"entity_{kind}_{forced_id}.jsonl"
        with msg_path.open("w", encoding="utf-8") as f:
            for m in msgs:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
    return entity


def _make_decomp_summary(d: Decomposition) -> str:
    """One-liner per entity, used as critic context."""
    parts: list[str] = []
    if d.races:
        parts.append("races:")
        for r in d.races:
            extra = f" (racial_skills={r.racial_skill_ids})" if r.racial_skill_ids else ""
            parts.append(f"  - {r.id}: {r.role}{extra}")
    if d.skills:
        parts.append("skills:")
        for s in d.skills:
            parts.append(f"  - {s.id} [{s.type}, {s.primary_stat}]: {s.role}")
    if d.locations:
        parts.append("locations:")
        for loc in d.locations:
            conn = (
                f" (connects: {', '.join(loc.connection_ids)})"
                if loc.connection_ids else ""
            )
            parts.append(f"  - {loc.id}: {loc.role}{conn}")
    if d.items:
        parts.append("items:")
        for it in d.items:
            owner = ""
            if it.owner_character_id:
                owner = f" (owner_character={it.owner_character_id})"
            elif it.owner_location_id:
                owner = f" (owner_location={it.owner_location_id})"
            elif it.for_player_template:
                owner = " (player start)"
            parts.append(f"  - {it.id} [{it.kind}]: {it.role}{owner}")
    if d.characters:
        parts.append("characters:")
        for c in d.characters:
            tag = "enemy" if c.is_enemy else "friendly"
            extra = f" (learned={c.learned_skill_ids})" if c.learned_skill_ids else ""
            parts.append(
                f"  - {c.id} [{tag}, race={c.race_id}, loc={c.location_id}]: {c.role}{extra}"
            )
    if d.quests:
        parts.append("quests:")
        for q in d.quests:
            prereq = f", prereq={q.prerequisite_ids}" if q.prerequisite_ids else ""
            parts.append(
                f"  - {q.id}: {q.role} (giver={q.giver_id}, trigger={q.trigger_kind}/{q.target_id}{prereq})"
            )
    if d.chapters:
        parts.append("chapters:")
        for ch in d.chapters:
            prereq = f", prereq={ch.prerequisite_ids}" if ch.prerequisite_ids else ""
            parts.append(f"  - {ch.id}: {ch.role} (quests={ch.quest_ids}{prereq})")
    return "\n".join(parts)


def _attach_step(scenario_dir: Path, decomp: Decomposition) -> None:
    """Final patch pass — fills cross-refs that were left empty in the
    skeleton writes. Pure data transform, no LLM.

    - race.racial_skill_ids ← decomp
    - location.item_ids ← items with matching owner_location_id
    - character.racial_skill_ids ← inherited from race
    - character.learned_skill_ids ← decomp
    - character.inventory_ids ← items owned by this character
    - character.equipment ← inferred from inventory:
      - Armor → `top` (single slot — first armor wins)
      - One-handed weapon → dominant hand
      - Two-handed weapon → both hands
    """
    races_dir = scenario_dir / "races"
    items_dir = scenario_dir / "items"
    chars_dir = scenario_dir / "characters"
    locs_dir = scenario_dir / "locations"
    if not (races_dir.exists() and chars_dir.exists()):
        return

    # Patch races first so character racial inheritance reads the final list.
    decomp_race = {r.id: r for r in decomp.races}
    for path in races_dir.glob("*.json"):
        race = json.loads(path.read_text(encoding="utf-8"))
        dr = decomp_race.get(race["id"])
        if dr is None:
            continue
        race["racial_skill_ids"] = list(dr.racial_skill_ids)
        path.write_text(
            json.dumps(race, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    items: dict[str, Item] = {}
    if items_dir.exists():
        for path in items_dir.glob("*.json"):
            items[path.stem] = Item.model_validate_json(path.read_text(encoding="utf-8"))

    # Location patches: item_ids (from item.owner_location_id) and connections
    # (symmetric closure of decomp's connection_ids — undirected graph).
    if locs_dir.exists():
        items_by_loc: dict[str, list[str]] = {}
        for it_decomp in decomp.items:
            if it_decomp.owner_location_id and it_decomp.id in items:
                items_by_loc.setdefault(it_decomp.owner_location_id, []).append(it_decomp.id)
        adj: dict[str, set[str]] = {loc.id: set() for loc in decomp.locations}
        for loc_dec in decomp.locations:
            for tid in loc_dec.connection_ids:
                adj.setdefault(loc_dec.id, set()).add(tid)
                adj.setdefault(tid, set()).add(loc_dec.id)
        for path in locs_dir.glob("*.json"):
            loc = json.loads(path.read_text(encoding="utf-8"))
            loc["item_ids"] = items_by_loc.get(loc["id"], [])
            loc["connections"] = [
                Connection(target_id=tid).model_dump()
                for tid in sorted(adj.get(loc["id"], set()))
            ]
            path.write_text(
                json.dumps(loc, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    items_by_owner: dict[str, list[Item]] = {}
    for c in decomp.characters:
        items_by_owner.setdefault(c.id, [])
    for it_decomp in decomp.items:
        owner = it_decomp.owner_character_id
        if owner and it_decomp.id in items:
            items_by_owner.setdefault(owner, []).append(items[it_decomp.id])

    decomp_char = {c.id: c for c in decomp.characters}
    for char_path in chars_dir.glob("*.json"):
        char = Character.model_validate_json(char_path.read_text(encoding="utf-8"))
        dc = decomp_char.get(char.id)
        race_skills = decomp_race[dc.race_id].racial_skill_ids if dc else []
        if dc is not None:
            char.racial_skill_ids = list(race_skills)
            char.learned_skill_ids = list(dc.learned_skill_ids)
        owned = items_by_owner.get(char.id, [])
        char.inventory_ids = [it.id for it in owned]
        # Three-slot equipment: weapon → weapon, ArmorEffect → armor (or
        # accessory if armor already taken — e.g. a shield alongside body
        # armor), decorative (effects=None) → accessory.
        for it in owned:
            eff = it.effects
            if isinstance(eff, WeaponEffect):
                char.equipment.weapon = char.equipment.weapon or it.id
            elif isinstance(eff, ArmorEffect):
                if char.equipment.armor is None:
                    char.equipment.armor = it.id
                elif char.equipment.accessory is None:
                    char.equipment.accessory = it.id
            elif eff is None:
                if char.equipment.accessory is None:
                    char.equipment.accessory = it.id
        char_path.write_text(
            char.model_dump_json(indent=2), encoding="utf-8"
        )


def _check_item_no_required(entity: BaseModel) -> None:
    """Seed items must leave `required` empty — Stats defaults every missing
    field to 10, so a partial constraint silently expands into a full one and
    blocks the owner whose stats include any sub-10 value."""
    if not isinstance(entity, Item):
        return
    if entity.required is not None:
        raise EntityWriterError(
            f"item {entity.id} 에 required 가 박혀 있음. 시드 단계 item 은 항상 required=null. "
            "Pydantic 의 Stats 는 비어 있는 stat 을 자동으로 10 으로 채우기 때문에 "
            "부분 객체로 보여도 owner 의 sub-10 stat 과 충돌해 invariant 가 잡는다."
        )


def _check_enemy_consistency(entity: BaseModel, expected_enemy: bool) -> None:
    if not isinstance(entity, Character):
        return
    has_combat = entity.combat_behavior is not None
    if expected_enemy and not has_combat:
        raise EntityWriterError(
            f"character {entity.id} 가 적대 (is_enemy=true) 로 분해됐으나 combat_behavior 가 없음. "
            "적대 character 는 combat_behavior 를 박아라 ({{attack_priority, flee_hp_percent}})."
        )
    if not expected_enemy and has_combat:
        raise EntityWriterError(
            f"character {entity.id} 가 비적대 (is_enemy=false) 로 분해됐으나 combat_behavior 가 박혀 있음. "
            "비적대 character 의 combat_behavior 는 비워라 (필드 자체를 생략)."
        )
    if expected_enemy and entity.xp_reward <= 0:
        raise EntityWriterError(
            f"character {entity.id} 가 적대 (is_enemy=true) 로 분해됐으나 xp_reward={entity.xp_reward} 임. "
            "적대 character 는 xp_reward 를 양수로 박아라 (level 기준 가이드: level 1 → 40~80, level 3 → 100~200, level 5+ → 250+)."
        )
    if not expected_enemy and entity.xp_reward > 0:
        raise EntityWriterError(
            f"character {entity.id} 가 비적대 (is_enemy=false) 로 분해됐으나 xp_reward={entity.xp_reward} 임. "
            "비적대 character 는 xp_reward 를 0 으로 두거나 생략하라 (런타임 기본값 0)."
        )


# --- pipeline --------------------------------------------------------------

async def build_scenario(
    *,
    prose_path: Path,
    scenario_dir: Path,
    agents_dir: Path,
    llm: LLMClient,
    on_step: Callable[[str], None] | None = None,
    run_dir: Path | None = None,
    think: bool = True,
) -> dict:
    """One prose file → a complete scenario directory.

    Output: world.md + 6 entity directories + profile.json + start.json + player_template.json.
    Aborts if `scenario_dir` already exists (no overwrite).
    """
    if scenario_dir.exists():
        raise EntityWriterError(
            f"{scenario_dir} already exists. Use a new name or delete it and retry."
        )
    scenario_dir.mkdir(parents=True)

    critic_prompt = agents_dir / "_critic.md"

    def _step(msg: str) -> None:
        if on_step is not None:
            on_step(msg)

    # 1. decompose (3 sequential phases — setup → cast → arc)
    _step("decompose step")
    prose = prose_path.read_text(encoding="utf-8")
    decomp, decomp_msgs = await decompose_prose(
        prose=prose, agents_dir=agents_dir, llm=llm, think=think,
    )
    decomp_summary = _make_decomp_summary(decomp)
    if run_dir is not None:
        (run_dir / "decompose.json").write_text(
            decomp.model_dump_json(indent=2), encoding="utf-8"
        )
        with (run_dir / "decompose_messages.jsonl").open("w", encoding="utf-8") as f:
            for m in decomp_msgs:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}

    # 2. world.md (free-form markdown)
    _step("world.md")
    (scenario_dir / "world.md").write_text(decomp.world_md, encoding="utf-8")

    # 3. races — skeleton; racial_skill_ids stays empty until the attach pass
    # so the skill writer can see actual race + character profiles on disk.
    _step(f"race × {len(decomp.races)}")
    for r in decomp.races:
        await _write_step(
            kind="race", forced_id=r.id,
            hint=_hint_with_id(r.id, r.role, "racial_skill_ids 는 [] 로 둘 것 (다음 단계에서 자동 채워진다)."),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
            skeleton=True,
        )
    counts["race"] = len(decomp.races)

    # 4. locations — skeleton; item_ids and connections stay empty until the
    # attach pass fills them programmatically.
    _step(f"location × {len(decomp.locations)}")
    for loc in decomp.locations:
        await _write_step(
            kind="location", forced_id=loc.id,
            hint=_hint_with_id(
                loc.id, loc.role,
                "item_ids 와 connections 는 모두 [] 로 둘 것 (다음 단계에서 자동 채워진다).",
            ),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
            skeleton=True,
        )
    counts["location"] = len(decomp.locations)

    # 5. characters — skeleton. inventory/equipment/skill_ids stay empty
    # until the attach pass (after items + skills are on disk).
    _step(f"character × {len(decomp.characters)}")
    for c in decomp.characters:
        if c.is_enemy:
            flag = (
                "적대 — combat_behavior 를 박아라 ({attack_priority, flee_hp_percent}). "
                "xp_reward 도 양수로 박아라 (level 1 → 40~80, level 3 → 100~200, level 5+ → 250+)."
            )
        else:
            flag = (
                "비적대 — combat_behavior 는 박지 말 것 (필드 자체 생략). "
                "xp_reward 는 0 또는 생략."
            )
        extra = (
            f"적대 여부: {flag}. "
            f"race_id 를 정확히 '{c.race_id}' 로 박을 것. "
            f"location_id 를 정확히 '{c.location_id}' 로 박을 것. "
            "inventory_ids, equipment, racial_skill_ids, learned_skill_ids 는 모두 비워둘 것 "
            "— 다음 단계에서 자동으로 채워진다."
        )
        expected_enemy = c.is_enemy

        def _check(entity: BaseModel, ee: bool = expected_enemy) -> None:
            _check_enemy_consistency(entity, ee)

        await _write_step(
            kind="character", forced_id=c.id,
            hint=_hint_with_id(c.id, c.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
            extra_check=_check, think=think, run_dir=run_dir,
            critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
            skeleton=True,
        )
    counts["character"] = len(decomp.characters)

    # 6. skills — race + character skeletons are on disk; pass each skill's
    # owners (race / character) so the writer can tailor name, description,
    # and special_effect to that owner's profile.
    _step(f"skill × {len(decomp.skills)}")
    skill_owners: dict[str, list[str]] = {}
    for r in decomp.races:
        for sid in r.racial_skill_ids:
            skill_owners.setdefault(sid, []).append(f"race:{r.id}")
    for c in decomp.characters:
        for sid in c.learned_skill_ids:
            skill_owners.setdefault(sid, []).append(f"character:{c.id}")
    for s in decomp.skills:
        owner_blurbs: list[str] = []
        is_racial = False
        char_owner_levels: list[int] = []
        for owner_ref in skill_owners.get(s.id, []):
            kind, oid = owner_ref.split(":", 1)
            path = scenario_dir / ("races" if kind == "race" else "characters") / f"{oid}.json"
            if not path.exists():
                continue
            owner = json.loads(path.read_text(encoding="utf-8"))
            if kind == "race":
                is_racial = True
                owner_blurbs.append(
                    f"race {oid}: name='{owner['name']}', description='{owner['description']}'"
                )
            else:
                lvl = owner.get("level")
                if isinstance(lvl, int):
                    char_owner_levels.append(lvl)
                owner_blurbs.append(
                    f"character {oid}: name='{owner['name']}', "
                    f"job='{owner.get('job','')}', level={lvl if lvl is not None else '?'}, "
                    f"role='{owner.get('role','')}'"
                )
        # Racial wins: any race owner forces level=1 (the racial level pin).
        # Otherwise the skill must fit the lowest-level character that learned it.
        if is_racial:
            forced_level = 1
            level_reason = "race 가 owner 인 racial skill — level 은 항상 1."
        elif char_owner_levels:
            forced_level = min(char_owner_levels)
            level_reason = (
                f"character owner 의 최저 level={forced_level} 이하여야 한다 "
                "(invariant: skill.level ≤ character.level)."
            )
        else:
            forced_level = 1
            level_reason = "owner 미상 — level 1 로 둘 것."
        extra = (
            f"primary_stat 을 정확히 '{s.primary_stat}' 로, "
            f"type 을 정확히 '{s.type}' 로, "
            f"level 을 정확히 {forced_level} 로 박아라. {level_reason}"
        )
        if owner_blurbs:
            extra += (
                f" 이 스킬을 쓰는 owner: {'; '.join(owner_blurbs)}. "
                "owner 의 직업·레벨·세계관에 어울리는 이름·description·special_effect 로."
            )

        def _check_skill_level(entity: BaseModel, fl: int = forced_level) -> None:
            level = getattr(entity, "level", None)
            if level != fl:
                raise EntityWriterError(
                    f"skill {entity.id} level={level} ≠ 강제 level={fl}. "
                    "힌트의 level 지시를 정확히 따라야 invariant (skill.level ≤ character.level) 을 통과한다."
                )

        await _write_step(
            kind="skill", forced_id=s.id,
            hint=_hint_with_id(s.id, s.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            extra_check=_check_skill_level,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["skill"] = len(decomp.skills)

    # 7. items — characters already on disk; load each item's owner profile
    # so the writer tailors armor/weapon to that character's job and level.
    _step(f"item × {len(decomp.items)}")
    char_by_id_decomp = {c.id: c for c in decomp.characters}
    for it in decomp.items:
        extra = f"분류: {it.kind} ('{it.kind}' 의 effects 모양 사용)."
        if it.owner_character_id and it.owner_character_id in char_by_id_decomp:
            owner_path = scenario_dir / "characters" / f"{it.owner_character_id}.json"
            if owner_path.exists():
                owner = json.loads(owner_path.read_text(encoding="utf-8"))
                extra += (
                    f" 소유자 character: id='{owner['id']}', name='{owner.get('name','')}', "
                    f"job='{owner.get('job','')}', level={owner.get('level','?')}, "
                    f"role='{owner.get('role','')}'. "
                    "이 character 의 직업·레벨·세계관에 어울리는 디테일로 작성하라."
                )
        await _write_step(
            kind="item", forced_id=it.id,
            hint=_hint_with_id(it.id, it.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            extra_check=_check_item_no_required,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["item"] = len(decomp.items)

    # 8. attach — patch race / character / location cross-refs that were
    # left empty in skeleton writes. Pure data transform, no LLM.
    _step("attach skills + equipment")
    _attach_step(scenario_dir, decomp)

    # 9. quests — status = active iff prerequisite_ids is empty (the opening
    # quest of the opening chapter); everything else starts locked and unlocks
    # at runtime when its prereq quests complete.
    _step(f"quest × {len(decomp.quests)}")
    for q in decomp.quests:
        status = "active" if not q.prerequisite_ids else "locked"
        prereq_repr = "[" + ", ".join(repr(pid) for pid in q.prerequisite_ids) + "]"
        extra = (
            f"title 은 '{q.title}'. "
            f"giver_id 를 정확히 '{q.giver_id}' 로 박을 것. "
            f"triggers 에 type='{q.trigger_kind}', target_id='{q.target_id}' 인 trigger 한 개를 박아라. "
            f"prerequisite_ids 에 정확히 {prereq_repr} 를 박아라. "
            f"status 는 '{status}'. "
            f"required 는 {str(q.required).lower()}."
        )
        await _write_step(
            kind="quest", forced_id=q.id, hint=_hint_with_id(q.id, q.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["quest"] = len(decomp.quests)

    # 10. chapters — each chapter holds its own quest_ids subset (decomp partitions
    # the quest set across chapters). Opening chapter (no prereq) starts active;
    # rest start locked and unlock at runtime when their prereq chapters complete.
    _step(f"chapter × {len(decomp.chapters)}")
    for ch in decomp.chapters:
        status = "active" if not ch.prerequisite_ids else "locked"
        ch_quest_repr = "[" + ", ".join(repr(qid) for qid in ch.quest_ids) + "]"
        ch_prereq_repr = "[" + ", ".join(repr(pid) for pid in ch.prerequisite_ids) + "]"
        extra = (
            f"title 은 '{ch.title}'. "
            f"quest_ids 에 정확히 {ch_quest_repr} 를 박아라. "
            f"prerequisite_ids 에 정확히 {ch_prereq_repr} 를 박아라. "
            f"status 는 '{status}'."
        )
        await _write_step(
            kind="chapter", forced_id=ch.id, hint=_hint_with_id(ch.id, ch.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["chapter"] = len(decomp.chapters)

    # 11. meta files (profile / start / player_template)
    _step("meta files (profile / start / player_template)")
    profile = {
        "id": scenario_dir.name,
        "name": decomp.profile_name,
        "description": decomp.profile_description,
    }
    (scenario_dir / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    start = {
        "start_location_id": decomp.start_location_id,
        "active_subject_id": decomp.start_subject_id,
        "active_quest_id": decomp.start_quest_id,
        "world_time": "0001-01-01T09:00:00",
    }
    (scenario_dir / "start.json").write_text(
        json.dumps(start, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    player_inv = [it.id for it in decomp.items if it.for_player_template]
    player_template = {
        "id": "player_01",
        "equipment": {},
        "inventory_ids": player_inv,
    }
    (scenario_dir / "player_template.json").write_text(
        json.dumps(player_template, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 12. final scenario-level invariant sweep
    _step("invariant sweep")
    violations = check_scenario(Scenario.from_dir(scenario_dir))
    if violations:
        raise EntityWriterError(
            "scenario invariant violation:\n" + "\n".join(violations)
        )

    return {
        "scenario_dir": str(scenario_dir),
        "counts": counts,
        "decompose_msgs_len": len(decomp_msgs),
    }
