"""줄글 → 시나리오 한 벌 — 분해 단계 + 단계 파이프라인."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from src.llm_client.client import LLMClient

from .runner import (
    ID_PATTERN,
    EntityWriterError,
    write_entity,
    write_entity_to_disk,
)


# --- 분해 스키마 ----------------------------------------------------------


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


class DecCharacter(BaseModel):
    id: str
    role: str
    is_enemy: bool = False
    location_id: str


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


# --- 분해 일관성 검증 ----------------------------------------------------


_TRIGGER_TARGET_KIND = {
    "character_death": "character",
    "location_enter": "location",
    "item_use": "item",
}


def _check_decomp(d: Decomposition) -> None:
    """분해 결과의 id 패턴·중복·cross-ref 검증."""

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

    # character.location_id 가 locations 안에 실재
    char_by_id = {c.id: c for c in d.characters}
    for c in d.characters:
        if c.location_id not in loc_ids:
            raise EntityWriterError(
                f"character {c.id} location_id={c.location_id!r} 가 locations 명단에 없음. "
                f"가능한 id: {sorted(loc_ids)}"
            )

    # start_subject 가 start_location 에 있어야 함
    start_subject_loc = char_by_id[d.start_subject_id].location_id
    if start_subject_loc != d.start_location_id:
        raise EntityWriterError(
            f"start_subject_id={d.start_subject_id!r} 의 location_id={start_subject_loc!r} 가 "
            f"start_location_id={d.start_location_id!r} 와 다름. "
            "게임 시작 시 active subject 는 시작 위치에 있어야 한다."
        )

    target_pools = {
        "character": char_ids,
        "location": loc_ids,
        "item": item_ids,
    }
    for q in d.quests:
        target_kind = _TRIGGER_TARGET_KIND[q.trigger_kind]
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

    # race_ids 사용 안 했지만 미래 검증용 (character.race_id 가 race 명단에 있는지 등)
    _ = race_ids


# --- 분해 단계 ----------------------------------------------------------


async def decompose_prose(
    *,
    prose: str,
    prompt_path: Path,
    llm: LLMClient,
    retries: int = 5,
) -> tuple[Decomposition, list[dict]]:
    """줄글 → Decomposition. 자기교정 5회 루프."""
    system = prompt_path.read_text(encoding="utf-8")
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prose},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=False)
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


# --- 단계 파이프라인 ---------------------------------------------------


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
) -> BaseModel:
    entity, _msgs = await write_entity(
        kind=kind,
        scenario_dir=scenario_dir,
        agents_dir=agents_dir,
        hint=hint,
        llm=llm,
        force_id=forced_id,
    )
    write_entity_to_disk(entity, scenario_dir, kind)
    return entity


async def build_scenario(
    *,
    prose_path: Path,
    scenario_dir: Path,
    decompose_prompt_path: Path,
    agents_dir: Path,
    llm: LLMClient,
    on_step: Callable[[str], None] | None = None,
    run_dir: Path | None = None,
) -> dict:
    """줄글 한 편 → 시나리오 디렉터리 한 벌.

    출력: world.md + 6 entity 디렉터리 + profile.json + start.json + player_template.json.
    `scenario_dir` 가 이미 있으면 에러 (덮어쓰지 않음).
    """
    if scenario_dir.exists():
        raise EntityWriterError(
            f"{scenario_dir} 가 이미 존재함. 새 이름을 쓰거나 삭제 후 재시도."
        )
    scenario_dir.mkdir(parents=True)

    def _step(msg: str) -> None:
        if on_step is not None:
            on_step(msg)

    # 1. 분해
    _step("분해 단계")
    prose = prose_path.read_text(encoding="utf-8")
    decomp, decomp_msgs = await decompose_prose(
        prose=prose, prompt_path=decompose_prompt_path, llm=llm,
    )
    if run_dir is not None:
        (run_dir / "decompose.json").write_text(
            decomp.model_dump_json(indent=2), encoding="utf-8"
        )
        with (run_dir / "decompose_messages.jsonl").open("w", encoding="utf-8") as f:
            for m in decomp_msgs:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}

    # 2. world.md (markdown 자유 텍스트)
    _step("world.md")
    (scenario_dir / "world.md").write_text(decomp.world_md, encoding="utf-8")

    # 3. races
    _step(f"race × {len(decomp.races)}")
    for r in decomp.races:
        await _write_step(
            kind="race", forced_id=r.id, hint=_hint_with_id(r.id, r.role),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
        )
    counts["race"] = len(decomp.races)

    # 4. locations
    _step(f"location × {len(decomp.locations)}")
    for loc in decomp.locations:
        await _write_step(
            kind="location", forced_id=loc.id, hint=_hint_with_id(loc.id, loc.role),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
        )
    counts["location"] = len(decomp.locations)

    # 5. items
    _step(f"item × {len(decomp.items)}")
    for it in decomp.items:
        extra = f"분류: {it.kind} ('{it.kind}' 의 effects 모양 사용)."
        await _write_step(
            kind="item", forced_id=it.id,
            hint=_hint_with_id(it.id, it.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
        )
    counts["item"] = len(decomp.items)

    # 6. characters
    _step(f"character × {len(decomp.characters)}")
    for c in decomp.characters:
        flag = "적대 (combat_behavior 박을 것)" if c.is_enemy else "비적대"
        extra = (
            f"적대 여부: {flag}. "
            f"location_id 를 정확히 '{c.location_id}' 로 박을 것."
        )
        await _write_step(
            kind="character", forced_id=c.id,
            hint=_hint_with_id(c.id, c.role, extra),
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
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
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
        )
    counts["quest"] = len(decomp.quests)

    # 8. chapters — 모든 quest 를 첫 chapter 에 묶음
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
            scenario_dir=scenario_dir, agents_dir=agents_dir, llm=llm,
        )
    counts["chapter"] = len(decomp.chapters)

    # 9. 메타 파일 3개
    _step("메타 파일 (profile / start / player_template)")
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

    player_template = {
        "id": "player_01",
        "equipment": {},
        "inventory_ids": [],
    }
    (scenario_dir / "player_template.json").write_text(
        json.dumps(player_template, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "scenario_dir": str(scenario_dir),
        "counts": counts,
        "decompose_msgs_len": len(decomp_msgs),
    }
