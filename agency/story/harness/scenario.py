"""Prose → a full scenario — decomposition step plus a per-kind pipeline."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from src.domain.entities import Character
from src.engines.invariants import Scenario, check
from src.llm import LLMClient

from .runner import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
    write_entity,
    write_entity_to_disk,
)


# --- decomposition schema --------------------------------------------------

class DecRace(BaseModel):
    id: str
    role: str


class DecLocation(BaseModel):
    id: str
    role: str


class DecItem(BaseModel):
    id: str
    kind: Literal["weapon", "armor", "consumable", "key"]
    role: str
    owner_character_id: str | None = None
    owner_location_id: str | None = None
    for_player_template: bool = False


class DecCharacter(BaseModel):
    id: str
    role: str
    is_enemy: bool = False
    location_id: str
    race_id: str


class DecQuest(BaseModel):
    id: str
    title: str
    trigger_kind: Literal["character_death", "location_enter", "item_use"]
    target_id: str
    giver_id: str
    role: str


class DecChapter(BaseModel):
    id: str
    title: str
    role: str


class Decomposition(BaseModel):
    world_md: str
    profile_name: str
    profile_description: str
    races: list[DecRace]
    locations: list[DecLocation]
    items: list[DecItem]
    characters: list[DecCharacter]
    quests: list[DecQuest]
    chapters: list[DecChapter]
    start_location_id: str
    start_subject_id: str
    start_quest_id: str


# --- decomposer ------------------------------------------------------------

def _check_decomp(d: Decomposition) -> None:
    def _check_ids(items: list, kind: str) -> set[str]:
        seen: set[str] = set()
        for item in items:
            if not ID_PATTERN.match(item.id):
                raise EntityWriterError(
                    f"{kind} id={item.id!r} 가 패턴에 안 맞음 (^[a-z][a-z0-9_]{{1,30}}$)."
                )
            if item.id in seen:
                raise EntityWriterError(f"{kind} id={item.id!r} 중복.")
            seen.add(item.id)
        return seen

    race_ids = _check_ids(d.races, "race")
    loc_ids = _check_ids(d.locations, "location")
    item_ids = _check_ids(d.items, "item")
    char_ids = _check_ids(d.characters, "character")
    quest_ids = _check_ids(d.quests, "quest")
    _check_ids(d.chapters, "chapter")

    if not d.chapters:
        raise EntityWriterError("chapters 가 비어 있음. 최소 1 개 필요.")
    if d.start_location_id not in loc_ids:
        raise EntityWriterError(
            f"start_location_id={d.start_location_id!r} 가 locations 명단에 없음. "
            f"가능한 id: {sorted(loc_ids)}"
        )
    if d.start_subject_id not in char_ids:
        raise EntityWriterError(
            f"start_subject_id={d.start_subject_id!r} 가 characters 명단에 없음."
        )
    if d.start_quest_id not in quest_ids:
        raise EntityWriterError(
            f"start_quest_id={d.start_quest_id!r} 가 quests 명단에 없음."
        )

    # character.location_id / race_id must point inside the manifest
    char_by_id = {c.id: c for c in d.characters}
    for c in d.characters:
        if c.location_id not in loc_ids:
            raise EntityWriterError(
                f"character {c.id} location_id={c.location_id!r} 가 locations 명단에 없음. "
                f"가능한 id: {sorted(loc_ids)}"
            )
        if c.race_id not in race_ids:
            raise EntityWriterError(
                f"character {c.id} race_id={c.race_id!r} 가 races 명단에 없음. "
                f"가능한 id: {sorted(race_ids)}"
            )

    # active subject must start at the start location
    start_subject_loc = char_by_id[d.start_subject_id].location_id
    if start_subject_loc != d.start_location_id:
        raise EntityWriterError(
            f"start_subject_id={d.start_subject_id!r} 의 location_id={start_subject_loc!r} 가 "
            f"start_location_id={d.start_location_id!r} 와 다름. "
            "게임 시작 시 active subject 는 시작 위치에 있어야 한다."
        )

    for it in d.items:
        if it.owner_character_id is not None and it.owner_character_id not in char_ids:
            raise EntityWriterError(
                f"item {it.id} owner_character_id={it.owner_character_id!r} 가 characters 명단에 없음."
            )
        if it.owner_location_id is not None and it.owner_location_id not in loc_ids:
            raise EntityWriterError(
                f"item {it.id} owner_location_id={it.owner_location_id!r} 가 locations 명단에 없음."
            )
        if it.owner_character_id is not None and it.owner_location_id is not None:
            raise EntityWriterError(
                f"item {it.id} 의 owner_character_id 와 owner_location_id 가 모두 있음. "
                "둘 중 하나만 (또는 for_player_template=true 면 둘 다 비워둘 수 있음)."
            )

    target_pools = {
        "character": char_ids,
        "location": loc_ids,
        "item": item_ids,
    }
    for q in d.quests:
        target_kind = TRIGGER_TARGET_KIND[q.trigger_kind]
        if q.target_id not in target_pools[target_kind]:
            raise EntityWriterError(
                f"quest {q.id} trigger_kind={q.trigger_kind} target_id={q.target_id!r} "
                f"가 {target_kind} 명단에 없음."
            )
        if q.giver_id not in char_ids:
            raise EntityWriterError(
                f"quest {q.id} giver_id={q.giver_id!r} 가 characters 명단에 없음."
            )
        giver = char_by_id[q.giver_id]
        if giver.is_enemy:
            raise EntityWriterError(
                f"quest {q.id} giver_id={q.giver_id!r} 가 적대 character (is_enemy=true) 임. "
                "의뢰자는 비적대여야 한다."
            )

async def decompose_prose(
    *,
    prose: str,
    prompt_path: Path,
    llm: LLMClient,
    retries: int = 5,
    think: bool = True,
) -> tuple[Decomposition, list[dict]]:
    """Prose → Decomposition. Same self-correction loop as write_entity."""
    system = prompt_path.read_text(encoding="utf-8")
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prose},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=think, agent="story_decompose")
        answer = (result["answer"] or "").strip()
        try:
            d = Decomposition.model_validate_json(answer)
            _check_decomp(d)
            return d, messages + [{"role": "assistant", "content": answer}]
        except (ValidationError, EntityWriterError, json.JSONDecodeError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"이전 응답이 검증에 실패했다: {e}. "
                        "규칙을 다시 읽고 수정된 JSON 만 출력하라."
                    ),
                }
            )
    assert last_error is not None
    raise last_error


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
            parts.append(f"  - {r.id}: {r.role}")
    if d.locations:
        parts.append("locations:")
        for loc in d.locations:
            parts.append(f"  - {loc.id}: {loc.role}")
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
            parts.append(f"  - {c.id} [{tag}, race={c.race_id}, loc={c.location_id}]: {c.role}")
    if d.quests:
        parts.append("quests:")
        for q in d.quests:
            parts.append(f"  - {q.id}: {q.role} (giver={q.giver_id}, trigger={q.trigger_kind}/{q.target_id})")
    if d.chapters:
        parts.append("chapters:")
        for ch in d.chapters:
            parts.append(f"  - {ch.id}: {ch.role}")
    return "\n".join(parts)


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
    decompose_prompt_path: Path,
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

    # 1. decompose
    _step("decompose step")
    prose = prose_path.read_text(encoding="utf-8")
    decomp, decomp_msgs = await decompose_prose(
        prose=prose, prompt_path=decompose_prompt_path, llm=llm, think=think,
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

    # 3. races
    _step(f"race × {len(decomp.races)}")
    for r in decomp.races:
        await _write_step(
            kind="race", forced_id=r.id, hint=_hint_with_id(r.id, r.role),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["race"] = len(decomp.races)

    # 4. items (before locations — location.item_ids and character.inventory_ids reference item ids)
    _step(f"item × {len(decomp.items)}")
    for it in decomp.items:
        extra = f"분류: {it.kind} ('{it.kind}' 의 effects 모양 사용)."
        await _write_step(
            kind="item", forced_id=it.id,
            hint=_hint_with_id(it.id, it.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["item"] = len(decomp.items)

    # 5. locations — items whose owner_location_id matches go into item_ids
    _step(f"location × {len(decomp.locations)}")
    items_by_loc: dict[str, list[str]] = {}
    for it in decomp.items:
        if it.owner_location_id:
            items_by_loc.setdefault(it.owner_location_id, []).append(it.id)
    for loc in decomp.locations:
        loc_items = items_by_loc.get(loc.id, [])
        if loc_items:
            items_repr = "[" + ", ".join(repr(i) for i in loc_items) + "]"
            extra = f"item_ids 에 정확히 {items_repr} 를 박아라."
        else:
            extra = "item_ids 는 빈 리스트 또는 생략."
        await _write_step(
            kind="location", forced_id=loc.id,
            hint=_hint_with_id(loc.id, loc.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["location"] = len(decomp.locations)

    # 6. characters — race_id, location_id, inventory_ids all forced
    _step(f"character × {len(decomp.characters)}")
    items_by_char: dict[str, list[str]] = {}
    for it in decomp.items:
        if it.owner_character_id:
            items_by_char.setdefault(it.owner_character_id, []).append(it.id)
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
        char_items = items_by_char.get(c.id, [])
        if char_items:
            inv_repr = "[" + ", ".join(repr(i) for i in char_items) + "]"
            inv_clause = f" inventory_ids 에 정확히 {inv_repr} 를 박을 것."
        else:
            inv_clause = " inventory_ids 는 빈 리스트 또는 생략."
        extra = (
            f"적대 여부: {flag}. "
            f"race_id 를 정확히 '{c.race_id}' 로 박을 것. "
            f"location_id 를 정확히 '{c.location_id}' 로 박을 것."
            f"{inv_clause}"
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
        )
    counts["character"] = len(decomp.characters)

    # 7. quests
    _step(f"quest × {len(decomp.quests)}")
    active_quest_id = decomp.start_quest_id
    for q in decomp.quests:
        status = "active" if q.id == active_quest_id else "locked"
        extra = (
            f"title 은 '{q.title}'. "
            f"giver_id 를 정확히 '{q.giver_id}' 로 박을 것. "
            f"triggers 에 type='{q.trigger_kind}', target_id='{q.target_id}' 인 trigger 한 개를 박아라. "
            f"status 는 '{status}'."
        )
        await _write_step(
            kind="quest", forced_id=q.id, hint=_hint_with_id(q.id, q.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["quest"] = len(decomp.quests)

    # 8. chapters — every quest gets bundled into the first chapter
    _step(f"chapter × {len(decomp.chapters)}")
    quest_id_list = [q.id for q in decomp.quests]
    quest_ids_repr = "[" + ", ".join(repr(qid) for qid in quest_id_list) + "]"
    for i, ch in enumerate(decomp.chapters):
        extra = (
            f"title 은 '{ch.title}'. "
            f"quest_ids 에 정확히 {quest_ids_repr} 를 박아라. "
            f"status 는 {'active' if i == 0 else 'locked'}."
        )
        await _write_step(
            kind="chapter", forced_id=ch.id, hint=_hint_with_id(ch.id, ch.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm, think=think,
            run_dir=run_dir, critic_prompt_path=critic_prompt, decomp_summary=decomp_summary,
        )
    counts["chapter"] = len(decomp.chapters)

    # 9. meta files (profile / start / player_template)
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

    # 10. final scenario-level invariant sweep
    _step("invariant sweep")
    violations = check.scenario(Scenario.from_dir(scenario_dir))
    if violations:
        raise EntityWriterError(
            "scenario invariant violation:\n" + "\n".join(violations)
        )

    return {
        "scenario_dir": str(scenario_dir),
        "counts": counts,
        "decompose_msgs_len": len(decomp_msgs),
    }
