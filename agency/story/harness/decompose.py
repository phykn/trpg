"""Prose → Decomposition. Phased decomposer used as the first step of build_scenario.

Three sequential LLM calls (setup → cast → arc), each with its own prompt
fragment, Pydantic schema, and validation. Phases compose into one
Decomposition that the build pipeline consumes.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from src.llm import LLMClient

from .runner import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
    strip_code_fences,
)


# --- decomposition schema --------------------------------------------------

class DecRace(BaseModel):
    id: str
    role: str
    racial_skill_ids: list[str] = []
    is_humanoid: bool


class DecLocation(BaseModel):
    id: str
    role: str
    connection_ids: list[str] = []


class DecItem(BaseModel):
    id: str
    kind: Literal["weapon", "armor", "consumable", "key"]
    role: str
    owner_character_id: str | None = None
    owner_location_id: str | None = None
    for_player_template: bool = False


class DecSkill(BaseModel):
    id: str
    role: str
    primary_stat: Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    type: Literal["attack", "heal", "buff", "debuff"]


class DecCharacter(BaseModel):
    id: str
    role: str
    is_enemy: bool = False
    location_id: str
    race_id: str
    learned_skill_ids: list[str] = []


class DecQuest(BaseModel):
    id: str
    title: str
    trigger_kind: Literal["character_death", "location_enter", "item_use"]
    target_id: str
    giver_id: str
    role: str
    prerequisite_ids: list[str] = []
    required: bool = True


class DecChapter(BaseModel):
    id: str
    title: str
    role: str
    quest_ids: list[str]
    prerequisite_ids: list[str] = []


class Decomposition(BaseModel):
    world_md: str
    profile_name: str
    profile_description: str
    races: list[DecRace]
    skills: list[DecSkill] = []
    locations: list[DecLocation]
    items: list[DecItem]
    characters: list[DecCharacter]
    quests: list[DecQuest]
    chapters: list[DecChapter]
    start_location_id: str
    start_subject_id: str
    start_quest_id: str


# --- phased decomposition models -------------------------------------------
# The decomposer runs three sequential LLM calls (setup → cast → arc) and the
# results compose into Decomposition above. Splitting reduces single-call
# output size and makes each retry self-contained.

class DecomSetup(BaseModel):
    """Phase A — world toolbox: races + skills + locations + start_location."""
    world_md: str
    profile_name: str
    profile_description: str
    races: list[DecRace]
    skills: list[DecSkill] = []
    locations: list[DecLocation]
    start_location_id: str


class DecomCast(BaseModel):
    """Phase B — characters + items + start_subject (race/location come from Phase A)."""
    characters: list[DecCharacter]
    items: list[DecItem]
    start_subject_id: str


class DecomArc(BaseModel):
    """Phase C — quests + chapters + start_quest_id."""
    quests: list[DecQuest]
    chapters: list[DecChapter]
    start_quest_id: str


def _compose_decomposition(
    setup: DecomSetup, cast: DecomCast, arc: DecomArc
) -> Decomposition:
    return Decomposition(
        world_md=setup.world_md,
        profile_name=setup.profile_name,
        profile_description=setup.profile_description,
        races=setup.races,
        skills=setup.skills,
        locations=setup.locations,
        items=cast.items,
        characters=cast.characters,
        quests=arc.quests,
        chapters=arc.chapters,
        start_location_id=setup.start_location_id,
        start_subject_id=cast.start_subject_id,
        start_quest_id=arc.start_quest_id,
    )


# --- decomposer ------------------------------------------------------------

def _check_no_cycle(
    *, nodes: set[str], edges: dict[str, list[str]], kind: str
) -> None:
    """DFS-based cycle detection over a prerequisite_ids DAG. Raises on first cycle."""
    visited: set[str] = set()
    on_stack: set[str] = set()

    def _dfs(nid: str, path: list[str]) -> list[str] | None:
        if nid in on_stack:
            return path[path.index(nid):] + [nid]
        if nid in visited:
            return None
        visited.add(nid)
        on_stack.add(nid)
        path.append(nid)
        for nb in edges.get(nid, []):
            if nb not in nodes:
                continue
            cyc = _dfs(nb, path)
            if cyc is not None:
                return cyc
        on_stack.remove(nid)
        path.pop()
        return None

    for nid in nodes:
        if nid in visited:
            continue
        cyc = _dfs(nid, [])
        if cyc is not None:
            raise EntityWriterError(
                f"{kind} prerequisite_ids 에 cycle 이 있음: {' → '.join(cyc)}"
            )


def _normalize_decomp(d: Decomposition) -> None:
    """Auto-correct deterministic data conflicts the LLM keeps producing.

    Items with both owner_character_id and owner_location_id set: the LLM
    sometimes redundantly fills the location of the NPC owner. NPC inventory
    is the more specific signal, so drop owner_location_id."""
    for it in d.items:
        if it.owner_character_id is not None and it.owner_location_id is not None:
            it.owner_location_id = None


def _check_ids(items: list, kind: str) -> set[str]:
    """Reject malformed/duplicate ids inside a single entity roster."""
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


def _check_setup(s: DecomSetup) -> None:
    """Phase A self-consistency: id patterns, location graph, racial skills."""
    race_ids = _check_ids(s.races, "race")
    skill_ids = _check_ids(s.skills, "skill")
    loc_ids = _check_ids(s.locations, "location")

    # Locations must form a connected map reachable from start_location_id.
    loc_by_id = {loc.id: loc for loc in s.locations}
    for loc in s.locations:
        seen_targets: set[str] = set()
        for tid in loc.connection_ids:
            if tid == loc.id:
                raise EntityWriterError(
                    f"location {loc.id} connection_ids 가 자기 자신을 가리킴. 자기-루프 금지."
                )
            if tid not in loc_by_id:
                raise EntityWriterError(
                    f"location {loc.id} connection_id={tid!r} 가 locations 명단에 없음. "
                    f"가능한 id: {sorted(loc_by_id)}"
                )
            if tid in seen_targets:
                raise EntityWriterError(
                    f"location {loc.id} connection_ids 에 {tid!r} 가 중복."
                )
            seen_targets.add(tid)
    if s.locations:
        # BFS over the undirected projection — both directions count for
        # reachability since attach makes connections symmetric.
        adj: dict[str, set[str]] = {loc.id: set() for loc in s.locations}
        for loc in s.locations:
            for tid in loc.connection_ids:
                adj[loc.id].add(tid)
                adj[tid].add(loc.id)
        if s.start_location_id in adj:
            visited: set[str] = {s.start_location_id}
            stack = [s.start_location_id]
            while stack:
                cur = stack.pop()
                for nb in adj[cur]:
                    if nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            unreachable = [lid for lid in adj if lid not in visited]
            if unreachable:
                raise EntityWriterError(
                    f"start_location_id={s.start_location_id!r} 에서 도달 불가능한 locations: "
                    f"{sorted(unreachable)}. 모든 location 이 connection_ids 를 통해 시작점에서 닿아야 한다."
                )
    if s.start_location_id not in loc_ids:
        raise EntityWriterError(
            f"start_location_id={s.start_location_id!r} 가 locations 명단에 없음. "
            f"가능한 id: {sorted(loc_ids)}"
        )

    # race.racial_skill_ids must reference declared skills, and every race
    # must declare ≥1 racial so plain villagers (with empty learned) still
    # satisfy the seed-only "NPC must have ≥1 skill" invariant.
    for r in s.races:
        if not r.racial_skill_ids:
            raise EntityWriterError(
                f"race {r.id} 의 racial_skill_ids 가 비어 있음. "
                "모든 race 는 racial 1 개 이상이 필요하다 (인간은 'barter' 같은 일상 능력, "
                "짐승은 'natural_armor' 같은 자연 무기). 모든 NPC 가 race 의 racial 을 자동 상속하므로 "
                "이게 있어야 평민도 skill 수 ≥ 1 을 만족한다."
            )
        for sid in r.racial_skill_ids:
            if sid not in skill_ids:
                raise EntityWriterError(
                    f"race {r.id} racial_skill_id={sid!r} 가 skills 명단에 없음. "
                    f"가능한 id: {sorted(skill_ids)}"
                )


def _check_cast(s: DecomSetup, c: DecomCast) -> None:
    """Phase B: characters/items cross-ref to Phase A + start_subject + ownership."""
    race_ids = {r.id for r in s.races}
    skill_ids = {sk.id for sk in s.skills}
    loc_ids = {l.id for l in s.locations}
    char_ids = _check_ids(c.characters, "character")
    item_ids = _check_ids(c.items, "item")
    char_by_id = {ch.id: ch for ch in c.characters}
    race_by_id = {r.id: r for r in s.races}

    for ch in c.characters:
        if ch.location_id not in loc_ids:
            raise EntityWriterError(
                f"character {ch.id} location_id={ch.location_id!r} 가 locations 명단에 없음. "
                f"가능한 id: {sorted(loc_ids)}"
            )
        if ch.race_id not in race_ids:
            raise EntityWriterError(
                f"character {ch.id} race_id={ch.race_id!r} 가 races 명단에 없음. "
                f"가능한 id: {sorted(race_ids)}"
            )
        for sid in ch.learned_skill_ids:
            if sid not in skill_ids:
                raise EntityWriterError(
                    f"character {ch.id} learned_skill_id={sid!r} 가 skills 명단에 없음. "
                    f"가능한 id: {sorted(skill_ids)}"
                )
        racial_pool = set(race_by_id[ch.race_id].racial_skill_ids)
        for sid in ch.learned_skill_ids:
            if sid in racial_pool:
                raise EntityWriterError(
                    f"character {ch.id} learned_skill_id={sid!r} 가 race={ch.race_id} 의 "
                    f"racial_skill_ids 에 이미 들어 있음. character 는 race 의 racial 을 자동 "
                    "상속하므로 learned 에 같은 id 를 또 박으면 중복이 된다 — 다른 skill id 로 바꿔라."
                )

    # active subject must start at the start location
    if c.start_subject_id not in char_ids:
        raise EntityWriterError(
            f"start_subject_id={c.start_subject_id!r} 가 characters 명단에 없음."
        )
    start_subject_loc = char_by_id[c.start_subject_id].location_id
    if start_subject_loc != s.start_location_id:
        raise EntityWriterError(
            f"start_subject_id={c.start_subject_id!r} 의 location_id={start_subject_loc!r} 가 "
            f"start_location_id={s.start_location_id!r} 와 다름. "
            "게임 시작 시 active subject 는 시작 위치에 있어야 한다."
        )

    for it in c.items:
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

    # Each humanoid character must own ≥1 armor item; combatants also a weapon.
    # Collect ALL violations and raise once, so the LLM can fix every missing
    # item in a single retry instead of grinding through them one-by-one (which
    # exhausts the 5-shot budget on large manifests).
    items_by_owner: dict[str, list[DecItem]] = {}
    for it in c.items:
        if it.owner_character_id:
            items_by_owner.setdefault(it.owner_character_id, []).append(it)
    # Race-level is_humanoid is the authoritative humanoid flag — keyword
    # matching on `role` was too brittle (LLM uses "포식자/생물/추적자" instead
    # of the dictionary words "짐승/괴수").
    beast_races = {r.id for r in s.races if not r.is_humanoid}
    missing_armor: list[str] = []
    missing_weapon: list[str] = []
    for ch in c.characters:
        if ch.race_id in beast_races:
            continue
        owned = items_by_owner.get(ch.id, [])
        if not any(it.kind == "armor" for it in owned):
            missing_armor.append(ch.id)
        if ch.is_enemy and not any(it.kind == "weapon" for it in owned):
            missing_weapon.append(ch.id)
    if missing_armor or missing_weapon:
        lines: list[str] = []
        if missing_armor:
            lines.append(
                f"다음 인간형 character 들이 owned armor item 이 없음: {missing_armor}. "
                "items 명단에 각각 kind='armor' + owner_character_id 인 옷을 1 개씩 추가하라."
            )
        if missing_weapon:
            lines.append(
                f"다음 적대 character 들이 owned weapon item 이 없음: {missing_weapon}. "
                "items 명단에 각각 kind='weapon' + owner_character_id 인 무기를 1 개씩 추가하라."
            )
        raise EntityWriterError("\n".join(lines))


def _check_arc(s: DecomSetup, c: DecomCast, a: DecomArc) -> None:
    """Phase C: quest/chapter graphs + start_quest + opening-chapter rules."""
    char_ids = {ch.id for ch in c.characters}
    item_ids = {it.id for it in c.items}
    loc_ids = {l.id for l in s.locations}
    char_by_id = {ch.id: ch for ch in c.characters}

    quest_ids = _check_ids(a.quests, "quest")
    chapter_ids = _check_ids(a.chapters, "chapter")
    if not a.chapters:
        raise EntityWriterError("chapters 가 비어 있음. 최소 1 개 필요.")

    target_pools = {
        "character": char_ids,
        "location": loc_ids,
        "item": item_ids,
    }
    for q in a.quests:
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
        if q.trigger_kind == "character_death":
            target_char = char_by_id.get(q.target_id)
            if target_char is not None and not target_char.is_enemy:
                raise EntityWriterError(
                    f"quest {q.id} 의 character_death trigger target_id={q.target_id!r} 가 "
                    "비적대 character 임. 죽음 trigger 는 적대 character (is_enemy=true) 만 가리킬 수 있다 "
                    "(비적대 NPC 는 정상 플레이에서 죽지 않으므로 quest 가 영원히 미완료가 된다)."
                )

    # Quest prerequisite_ids — must point inside quests, no self-loop, no cycles.
    quest_by_id = {q.id: q for q in a.quests}
    for q in a.quests:
        seen_pid: set[str] = set()
        for pid in q.prerequisite_ids:
            if pid == q.id:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids 가 자기 자신을 가리킴. 자기-루프 금지."
                )
            if pid in seen_pid:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids 에 {pid!r} 가 중복."
                )
            seen_pid.add(pid)
            if pid not in quest_ids:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids 의 {pid!r} 가 quests 명단에 없음."
                )
    _check_no_cycle(
        nodes=quest_ids,
        edges={q.id: list(q.prerequisite_ids) for q in a.quests},
        kind="quest",
    )

    # Each quest must belong to exactly one chapter (chapter.quest_ids partitions
    # the quest set).
    quest_to_chapter: dict[str, str] = {}
    for ch in a.chapters:
        for qid in ch.quest_ids:
            if qid not in quest_ids:
                raise EntityWriterError(
                    f"chapter {ch.id} quest_ids 의 {qid!r} 가 quests 명단에 없음."
                )
            if qid in quest_to_chapter:
                raise EntityWriterError(
                    f"quest {qid!r} 가 두 chapter ({quest_to_chapter[qid]}, {ch.id}) 에 동시에 들어가 있음. "
                    "한 quest 는 정확히 한 chapter 에만 속해야 한다."
                )
            quest_to_chapter[qid] = ch.id
    unassigned = sorted(quest_ids - quest_to_chapter.keys())
    if unassigned:
        raise EntityWriterError(
            f"quest {unassigned} 가 어떤 chapter 에도 안 속해 있음. "
            "각 chapter 의 quest_ids 에 모든 quest 를 빠짐없이 분배하라."
        )

    # Chapter prerequisite_ids — same shape as quest, plus opening-chapter rule.
    for ch in a.chapters:
        seen_pid = set()
        for pid in ch.prerequisite_ids:
            if pid == ch.id:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids 가 자기 자신을 가리킴. 자기-루프 금지."
                )
            if pid in seen_pid:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids 에 {pid!r} 가 중복."
                )
            seen_pid.add(pid)
            if pid not in chapter_ids:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids 의 {pid!r} 가 chapters 명단에 없음."
                )
    _check_no_cycle(
        nodes=chapter_ids,
        edges={ch.id: list(ch.prerequisite_ids) for ch in a.chapters},
        kind="chapter",
    )

    if a.start_quest_id not in quest_ids:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} 가 quests 명단에 없음."
        )
    opening_chapter_id = quest_to_chapter[a.start_quest_id]
    opening_chapter = next(ch for ch in a.chapters if ch.id == opening_chapter_id)
    if opening_chapter.prerequisite_ids:
        raise EntityWriterError(
            f"chapter {opening_chapter.id} 가 start_quest_id={a.start_quest_id!r} 를 갖고 있는데 "
            f"prerequisite_ids={opening_chapter.prerequisite_ids} 가 비어 있지 않음. "
            "시작 chapter 는 prereq 가 없어야 한다 (게임 시작 시 active 로 진입해야 하므로)."
        )

    start_q = quest_by_id[a.start_quest_id]
    if start_q.prerequisite_ids:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} 의 prerequisite_ids={start_q.prerequisite_ids} 가 "
            "비어 있지 않음. 시작 quest 는 prereq 가 없어야 한다."
        )
    if not start_q.required:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} 의 required=false 임. 시작 quest 는 "
            "required=true 여야 한다 (그래야 chapter 진행도에 카운트되어 ch1 이 정상 종료된다)."
        )
    for qid in opening_chapter.quest_ids:
        if qid == a.start_quest_id:
            continue
        if not quest_by_id[qid].prerequisite_ids:
            raise EntityWriterError(
                f"quest {qid!r} 가 opening chapter ({opening_chapter.id}) 안에 있지만 "
                "prerequisite_ids 가 비어 있음. 시작 chapter 의 비-시작 quest 는 prereq 를 통해 "
                "플레이 도중에 자연스럽게 풀려야 한다 (게임 시작부터 모두 active 로 보이면 안 된다)."
            )


def _check_decomp(d: Decomposition) -> None:
    """Final paranoia check on the composed Decomposition. Reconstructs the
    three phase wrappers and runs each phase check — every rule that fires
    during the phased build also fires here."""
    setup = DecomSetup(
        world_md=d.world_md,
        profile_name=d.profile_name,
        profile_description=d.profile_description,
        races=d.races,
        skills=d.skills,
        locations=d.locations,
        start_location_id=d.start_location_id,
    )
    cast = DecomCast(
        characters=d.characters,
        items=d.items,
        start_subject_id=d.start_subject_id,
    )
    arc = DecomArc(
        quests=d.quests,
        chapters=d.chapters,
        start_quest_id=d.start_quest_id,
    )
    _check_setup(setup)
    _check_cast(setup, cast)
    _check_arc(setup, cast, arc)


async def _decompose_phase(
    *,
    fragment_path: Path,
    prose: str,
    prior_context: str | None,
    model: type[BaseModel],
    check: Callable[[BaseModel], None],
    agent: str,
    llm: LLMClient,
    retries: int,
    think: bool,
) -> tuple[BaseModel, list[dict]]:
    """One decompose phase: build system prompt (fragment + optional prior phase
    context), call the LLM, validate, retry up to `retries` times with the same
    base+latest trim used elsewhere."""
    system_parts = [fragment_path.read_text(encoding="utf-8")]
    if prior_context:
        system_parts.append("")
        system_parts.append("---")
        system_parts.append("")
        system_parts.append("## 이전 phase 에서 결정된 entity 명단")
        system_parts.append("")
        system_parts.append(
            "아래 JSON 의 id 와 명단을 그대로 참조하라. 새로 만들지 말고 기존 풀에서 골라라."
        )
        system_parts.append("")
        system_parts.append(prior_context)
    messages: list[dict] = [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": prose},
    ]
    base_len = len(messages)
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=think, agent=agent)
        answer = strip_code_fences(result["answer"] or "")
        try:
            entity = model.model_validate_json(answer)
            check(entity)
            return entity, messages + [{"role": "assistant", "content": answer}]
        except (ValidationError, EntityWriterError, json.JSONDecodeError) as e:
            last_error = e
            messages = messages[:base_len]
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


async def decompose_prose(
    *,
    prose: str,
    agents_dir: Path,
    llm: LLMClient,
    retries: int = 5,
    think: bool = True,
) -> tuple[Decomposition, list[dict]]:
    """Prose → Decomposition via 3 sequential phases (setup → cast → arc).

    Each phase has its own LLM call, prompt fragment, and validation — output
    sizes per call stay bounded and a retry on phase N doesn't restart phases
    1..N-1. Final composed Decomposition still goes through `_check_decomp`
    as a paranoia step.
    """
    setup, setup_msgs = await _decompose_phase(
        fragment_path=agents_dir / "_decompose_setup.md",
        prose=prose,
        prior_context=None,
        model=DecomSetup,
        check=_check_setup,
        agent="story_decompose_setup",
        llm=llm,
        retries=retries,
        think=think,
    )
    assert isinstance(setup, DecomSetup)

    # Setup context for phase B excludes world_md (free-form, large) — phase B
    # only needs the entity rosters as id pools.
    setup_ctx = setup.model_dump_json(indent=2, exclude={"world_md"})
    cast, cast_msgs = await _decompose_phase(
        fragment_path=agents_dir / "_decompose_cast.md",
        prose=prose,
        prior_context=setup_ctx,
        model=DecomCast,
        check=lambda c: _check_cast(setup, c),
        agent="story_decompose_cast",
        llm=llm,
        retries=retries,
        think=think,
    )
    assert isinstance(cast, DecomCast)

    cast_ctx = (
        f"### Phase A (setup)\n{setup_ctx}\n\n"
        f"### Phase B (cast)\n{cast.model_dump_json(indent=2)}"
    )
    arc, arc_msgs = await _decompose_phase(
        fragment_path=agents_dir / "_decompose_arc.md",
        prose=prose,
        prior_context=cast_ctx,
        model=DecomArc,
        check=lambda a: _check_arc(setup, cast, a),
        agent="story_decompose_arc",
        llm=llm,
        retries=retries,
        think=think,
    )
    assert isinstance(arc, DecomArc)

    d = _compose_decomposition(setup, cast, arc)
    _normalize_decomp(d)
    _check_decomp(d)  # paranoia: every phase rule re-fires here
    return d, setup_msgs + cast_msgs + arc_msgs
