"""Generic entity writer — LLM 호출 + Pydantic 검증 + 자기교정 루프 + 디스크 쓰기."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.domain.entities import Chapter, Character, Item, Location, Quest, Race
from src.llm_client.client import LLMClient

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class EntityWriterError(Exception):
    """semantic 검증 / 디스크 충돌 에러."""


def _noop_check(entity: BaseModel, refs: dict[str, set[str]]) -> None:
    return None


@dataclass(frozen=True)
class EntitySpec:
    kind: str
    model: type[BaseModel]
    sub_dir: str
    fragment: str
    ref_kinds: tuple[str, ...] = ()
    check_refs: Callable[[BaseModel, dict[str, set[str]]], None] = field(
        default=_noop_check
    )


def _check_location_refs(loc: Location, refs: dict[str, set[str]]) -> None:
    location_ids = refs.get("location", set())
    for c in loc.connections:
        if c.target_id == loc.id:
            raise EntityWriterError(
                f"location.connections 가 자기 자신({loc.id}) 을 가리킴"
            )
        if c.target_id not in location_ids:
            raise EntityWriterError(
                f"location.connections.target_id={c.target_id!r} 가 시나리오 locations 에 없음. "
                f"가능한 id: {sorted(location_ids)}"
            )


def _check_character_refs(ch: Character, refs: dict[str, set[str]]) -> None:
    races = refs.get("race", set())
    if ch.race_id not in races:
        raise EntityWriterError(
            f"character.race_id={ch.race_id!r} 가 시나리오 races 에 없음. "
            f"가능한 id: {sorted(races)}"
        )
    locations = refs.get("location", set())
    if ch.location_id is not None and ch.location_id not in locations:
        raise EntityWriterError(
            f"character.location_id={ch.location_id!r} 가 시나리오 locations 에 없음. "
            f"가능한 id: {sorted(locations)}"
        )
    items = refs.get("item", set())
    for iid in ch.inventory_ids:
        if iid not in items:
            raise EntityWriterError(
                f"character.inventory_ids 의 {iid!r} 가 시나리오 items 에 없음."
            )
    for slot, iid in ch.equipment.model_dump().items():
        if iid is not None and iid not in items:
            raise EntityWriterError(
                f"character.equipment.{slot}={iid!r} 가 시나리오 items 에 없음."
            )


_TRIGGER_TARGET_KIND = {
    "character_death": "character",
    "location_enter": "location",
    "item_use": "item",
}


def _check_quest_refs(q: Quest, refs: dict[str, set[str]]) -> None:
    characters = refs.get("character", set())
    if q.giver_id not in characters:
        raise EntityWriterError(
            f"quest.giver_id={q.giver_id!r} 가 시나리오 characters 에 없음."
        )
    for t in [*q.triggers, *q.fail_triggers]:
        target_kind = _TRIGGER_TARGET_KIND.get(t.type)
        if target_kind is None:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) type={t.type!r} 알 수 없음. "
                f"가능한 값: {sorted(_TRIGGER_TARGET_KIND)}"
            )
        pool = refs.get(target_kind, set())
        if t.target_id not in pool:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) target_id={t.target_id!r} 가 "
                f"{target_kind} 풀에 없음."
            )
    quests = refs.get("quest", set())
    for pid in q.prerequisite_ids:
        if pid not in quests:
            raise EntityWriterError(
                f"quest.prerequisite_ids 의 {pid!r} 가 시나리오 quests 에 없음."
            )


def _check_chapter_refs(ch: Chapter, refs: dict[str, set[str]]) -> None:
    quests = refs.get("quest", set())
    for qid in ch.quest_ids:
        if qid not in quests:
            raise EntityWriterError(
                f"chapter.quest_ids 의 {qid!r} 가 시나리오 quests 에 없음."
            )


SPECS: dict[str, EntitySpec] = {
    "race": EntitySpec(
        kind="race", model=Race, sub_dir="races", fragment="race.md",
    ),
    "location": EntitySpec(
        kind="location", model=Location, sub_dir="locations", fragment="location.md",
        ref_kinds=("location",), check_refs=_check_location_refs,
    ),
    "item": EntitySpec(
        kind="item", model=Item, sub_dir="items", fragment="item.md",
    ),
    "character": EntitySpec(
        kind="character", model=Character, sub_dir="characters", fragment="character.md",
        ref_kinds=("race", "location", "item"), check_refs=_check_character_refs,
    ),
    "quest": EntitySpec(
        kind="quest", model=Quest, sub_dir="quests", fragment="quest.md",
        ref_kinds=("character", "location", "item", "quest"),
        check_refs=_check_quest_refs,
    ),
    "chapter": EntitySpec(
        kind="chapter", model=Chapter, sub_dir="chapters", fragment="chapter.md",
        ref_kinds=("quest",), check_refs=_check_chapter_refs,
    ),
}


def _load_dir(scenario_dir: Path, sub_dir: str) -> list[dict]:
    d = scenario_dir / sub_dir
    if not d.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def _build_system(
    *,
    base_path: Path,
    fragment_path: Path,
    scenario_dir: Path,
    spec: EntitySpec,
) -> str:
    parts = [
        base_path.read_text(encoding="utf-8"),
        "",
        "---",
        "",
        fragment_path.read_text(encoding="utf-8"),
        "",
        "---",
        "",
        "## 시나리오 world.md",
        "",
        (scenario_dir / "world.md").read_text(encoding="utf-8"),
        "",
        f"## 기존 {spec.kind} 목록 (JSON)",
        "",
        json.dumps(_load_dir(scenario_dir, spec.sub_dir), ensure_ascii=False, indent=2),
    ]
    for ref_kind in spec.ref_kinds:
        if ref_kind == spec.kind:
            continue
        ref_spec = SPECS[ref_kind]
        parts.append("")
        parts.append(f"## 참조용 {ref_kind} 목록 (JSON)")
        parts.append("")
        parts.append(
            json.dumps(
                _load_dir(scenario_dir, ref_spec.sub_dir), ensure_ascii=False, indent=2
            )
        )
    return "\n".join(parts)


def _collect_refs(scenario_dir: Path, spec: EntitySpec) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {
        spec.kind: {e["id"] for e in _load_dir(scenario_dir, spec.sub_dir)}
    }
    for rk in spec.ref_kinds:
        if rk == spec.kind:
            continue
        refs[rk] = {e["id"] for e in _load_dir(scenario_dir, SPECS[rk].sub_dir)}
    return refs


def _check_id(
    entity: BaseModel, existing: set[str], force_id: str | None = None
) -> None:
    eid: str = entity.id  # type: ignore[attr-defined]
    if not ID_PATTERN.match(eid):
        raise EntityWriterError(
            f"id={eid!r} 가 패턴에 안 맞음. ASCII snake_case ([a-z][a-z0-9_]{{1,30}}) 필요."
        )
    if force_id is not None and eid != force_id:
        raise EntityWriterError(
            f"id={eid!r} 가 강제된 id={force_id!r} 와 다름. "
            f"hint 의 id 지시를 정확히 따라야 한다 — 한 글자도 바꾸지 말 것."
        )
    if eid in existing:
        raise EntityWriterError(
            f"id={eid!r} 가 기존과 겹침. 기존: {sorted(existing)}"
        )


async def write_entity(
    *,
    kind: str,
    scenario_dir: Path,
    agents_dir: Path,
    hint: str,
    llm: LLMClient,
    retries: int = 5,
    force_id: str | None = None,
) -> tuple[BaseModel, list[dict]]:
    """LLM 으로 entity 한 개 생성. 검증 실패 시 자기교정 루프 (retries 회)."""
    if kind not in SPECS:
        raise EntityWriterError(
            f"알 수 없는 kind: {kind!r}. 가능한 값: {sorted(SPECS)}"
        )
    spec = SPECS[kind]
    base_path = agents_dir / "_base.md"
    fragment_path = agents_dir / spec.fragment

    refs = _collect_refs(scenario_dir, spec)
    existing_ids = refs[spec.kind]

    system = _build_system(
        base_path=base_path,
        fragment_path=fragment_path,
        scenario_dir=scenario_dir,
        spec=spec,
    )
    user_msg = (
        hint.strip()
        if hint
        else f"(힌트 없음 — 자체 판단으로 {spec.kind} 한 개 만들기.)"
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=False)
        answer = (result["answer"] or "").strip()
        try:
            entity = spec.model.model_validate_json(answer)
            _check_id(entity, existing_ids, force_id=force_id)
            spec.check_refs(entity, refs)
            return entity, messages + [{"role": "assistant", "content": answer}]
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


def write_entity_to_disk(entity: BaseModel, scenario_dir: Path, kind: str) -> Path:
    """scenarios/<scenario>/<sub_dir>/<id>.json 으로 저장. 이미 있으면 EntityWriterError."""
    spec = SPECS[kind]
    eid: str = entity.id  # type: ignore[attr-defined]
    out_path = scenario_dir / spec.sub_dir / f"{eid}.json"
    if out_path.exists():
        raise EntityWriterError(f"{out_path} 가 이미 존재함. 덮어쓰지 않음.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(entity.model_dump_json(indent=2), encoding="utf-8")
    return out_path
