"""Prose → a full scenario — decomposition step plus a per-kind pipeline."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from src.domain.entities import (
    ArmorEffect,
    Character,
    Connection,
    Item,
    WeaponEffect,
)
from src.engines.invariants import Scenario, check_scenario
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
    racial_skill_ids: list[str] = []


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


class DecChapter(BaseModel):
    id: str
    title: str
    role: str


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


# --- decomposer ------------------------------------------------------------

def _normalize_decomp(d: Decomposition) -> None:
    """Auto-correct deterministic data conflicts the LLM keeps producing.

    Items with both owner_character_id and owner_location_id set: the LLM
    sometimes redundantly fills the location of the NPC owner. NPC inventory
    is the more specific signal, so drop owner_location_id."""
    for it in d.items:
        if it.owner_character_id is not None and it.owner_location_id is not None:
            it.owner_location_id = None


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
    skill_ids = _check_ids(d.skills, "skill")
    loc_ids = _check_ids(d.locations, "location")
    item_ids = _check_ids(d.items, "item")
    char_ids = _check_ids(d.characters, "character")
    quest_ids = _check_ids(d.quests, "quest")
    _check_ids(d.chapters, "chapter")

    if not d.chapters:
        raise EntityWriterError("chapters 가 비어 있음. 최소 1 개 필요.")
    # Locations must form a connected map reachable from start_location_id —
    # otherwise the player can never visit some quest targets.
    loc_by_id = {loc.id: loc for loc in d.locations}
    for loc in d.locations:
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
    if d.locations:
        # BFS over the undirected projection of connection_ids — both directions
        # count for reachability since attach makes connections symmetric.
        adj: dict[str, set[str]] = {loc.id: set() for loc in d.locations}
        for loc in d.locations:
            for tid in loc.connection_ids:
                adj[loc.id].add(tid)
                adj[tid].add(loc.id)
        if d.start_location_id in adj:
            visited: set[str] = {d.start_location_id}
            stack = [d.start_location_id]
            while stack:
                cur = stack.pop()
                for nb in adj[cur]:
                    if nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            unreachable = [lid for lid in adj if lid not in visited]
            if unreachable:
                raise EntityWriterError(
                    f"start_location_id={d.start_location_id!r} 에서 도달 불가능한 locations: "
                    f"{sorted(unreachable)}. 모든 location 이 connection_ids 를 통해 시작점에서 닿아야 한다."
                )
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

    # race.racial_skill_ids must reference declared skills, and every race
    # must declare ≥1 racial so plain villagers (with empty learned) still
    # satisfy the seed-only "NPC must have ≥1 skill" invariant.
    for r in d.races:
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

    # character.location_id / race_id / learned_skill_ids must point inside the manifest
    char_by_id = {c.id: c for c in d.characters}
    race_by_id = {r.id: r for r in d.races}
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
        for sid in c.learned_skill_ids:
            if sid not in skill_ids:
                raise EntityWriterError(
                    f"character {c.id} learned_skill_id={sid!r} 가 skills 명단에 없음. "
                    f"가능한 id: {sorted(skill_ids)}"
                )
        # learned must not overlap with the inherited racial pool — character
        # would end up holding the same skill id twice (duplicate violation).
        racial_pool = set(race_by_id[c.race_id].racial_skill_ids)
        for sid in c.learned_skill_ids:
            if sid in racial_pool:
                raise EntityWriterError(
                    f"character {c.id} learned_skill_id={sid!r} 가 race={c.race_id} 의 "
                    f"racial_skill_ids 에 이미 들어 있음. character 는 race 의 racial 을 자동 "
                    "상속하므로 learned 에 같은 id 를 또 박으면 중복이 된다 — 다른 skill id 로 바꿔라."
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

    # Each humanoid character must own ≥1 armor item; combatants also a weapon.
    items_by_owner: dict[str, list[DecItem]] = {}
    for it in d.items:
        if it.owner_character_id:
            items_by_owner.setdefault(it.owner_character_id, []).append(it)
    beast_races = {r.id for r in d.races if any(
        kw in r.role for kw in ("짐승", "괴수", "괴생명체", "짐승형", "야수")
    )}
    for c in d.characters:
        if c.race_id in beast_races:
            continue
        owned = items_by_owner.get(c.id, [])
        has_armor = any(it.kind == "armor" for it in owned)
        if not has_armor:
            raise EntityWriterError(
                f"character {c.id} (race={c.race_id}) 가 owned armor item 이 없음. "
                "items 명단에 kind='armor' + owner_character_id 인 옷을 1 개 넣어라."
            )
        if c.is_enemy:
            has_weapon = any(it.kind == "weapon" for it in owned)
            if not has_weapon:
                raise EntityWriterError(
                    f"character {c.id} 가 적대 (is_enemy=true) 인데 owned weapon item 이 없음. "
                    "items 명단에 kind='weapon' + owner_character_id 인 무기를 1 개 넣어라."
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
            _normalize_decomp(d)
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
            parts.append(f"  - {q.id}: {q.role} (giver={q.giver_id}, trigger={q.trigger_kind}/{q.target_id})")
    if d.chapters:
        parts.append("chapters:")
        for ch in d.chapters:
            parts.append(f"  - {ch.id}: {ch.role}")
    return "\n".join(parts)


def _attach_step(scenario_dir: Path, decomp: "Decomposition") -> None:
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
        for it in owned:
            eff = it.effects
            if isinstance(eff, WeaponEffect):
                if eff.two_handed:
                    char.equipment.leftHand = it.id
                    char.equipment.rightHand = it.id
                elif char.dominant_hand == "left":
                    char.equipment.leftHand = char.equipment.leftHand or it.id
                else:
                    char.equipment.rightHand = char.equipment.rightHand or it.id
            elif isinstance(eff, ArmorEffect):
                if char.equipment.top is None:
                    char.equipment.top = it.id
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
