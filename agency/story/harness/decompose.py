"""Decomposition data shapes + validators.

Pydantic models (DecomSetup/Cast/Arc and entity records) plus the per-phase
validators (_check_setup/_check_cast/_check_arc) used by `agency.story.tool`.
The LLM call loop that originally produced these decompositions has been
removed — Claude Code now writes them directly per agency/story/SKILL.md.
"""

from typing import Literal

from pydantic import BaseModel

from ._common import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
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
                f"{kind} prerequisite_ids has a cycle: {' → '.join(cyc)}"
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
                f"{kind} id={item.id!r} does not match the required pattern (^[a-z][a-z0-9_]{{1,30}}$)."
            )
        if item.id in seen:
            raise EntityWriterError(f"{kind} id={item.id!r} is duplicated.")
        seen.add(item.id)
    return seen


def _check_setup(s: DecomSetup) -> None:
    """Phase A self-consistency: id patterns, location graph, racial skills."""
    _check_ids(s.races, "race")  # validates id pattern + duplicates; result unused here
    skill_ids = _check_ids(s.skills, "skill")
    loc_ids = _check_ids(s.locations, "location")

    # Locations must form a connected map reachable from start_location_id.
    loc_by_id = {loc.id: loc for loc in s.locations}
    for loc in s.locations:
        seen_targets: set[str] = set()
        for tid in loc.connection_ids:
            if tid == loc.id:
                raise EntityWriterError(
                    f"location {loc.id} connection_ids points at itself. Self-loops are forbidden."
                )
            if tid not in loc_by_id:
                raise EntityWriterError(
                    f"location {loc.id} connection_id={tid!r} not found in the locations roster. "
                    f"Valid ids: {sorted(loc_by_id)}"
                )
            if tid in seen_targets:
                raise EntityWriterError(
                    f"location {loc.id} connection_ids has duplicate entry {tid!r}."
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
                    f"locations unreachable from start_location_id={s.start_location_id!r}: "
                    f"{sorted(unreachable)}. Every location must be reachable from the start via connection_ids."
                )
    if s.start_location_id not in loc_ids:
        raise EntityWriterError(
            f"start_location_id={s.start_location_id!r} not found in the locations roster. "
            f"Valid ids: {sorted(loc_ids)}"
        )

    # race.racial_skill_ids must reference declared skills, and every race
    # must declare ≥1 racial so plain villagers (with empty learned) still
    # satisfy the seed-only "NPC must have ≥1 skill" invariant.
    for r in s.races:
        if not r.racial_skill_ids:
            raise EntityWriterError(
                f"race {r.id} has empty racial_skill_ids. "
                "Every race needs at least one racial skill (humans get an everyday ability like 'barter'; "
                "beasts get a natural weapon like 'natural_armor'). Since every NPC inherits its race's "
                "racials automatically, this is what lets even commoners satisfy the seed-only invariant 'NPC must have ≥1 skill'."
            )
        for sid in r.racial_skill_ids:
            if sid not in skill_ids:
                raise EntityWriterError(
                    f"race {r.id} racial_skill_id={sid!r} not found in the skills roster. "
                    f"Valid ids: {sorted(skill_ids)}"
                )


def _check_cast(s: DecomSetup, c: DecomCast) -> None:
    """Phase B: characters/items cross-ref to Phase A + start_subject + ownership."""
    race_ids = {r.id for r in s.races}
    skill_ids = {sk.id for sk in s.skills}
    loc_ids = {loc.id for loc in s.locations}
    char_ids = _check_ids(c.characters, "character")
    _check_ids(c.items, "item")  # validates id pattern + duplicates; result unused here
    char_by_id = {ch.id: ch for ch in c.characters}
    race_by_id = {r.id: r for r in s.races}

    for ch in c.characters:
        if ch.location_id not in loc_ids:
            raise EntityWriterError(
                f"character {ch.id} location_id={ch.location_id!r} not found in the locations roster. "
                f"Valid ids: {sorted(loc_ids)}"
            )
        if ch.race_id not in race_ids:
            raise EntityWriterError(
                f"character {ch.id} race_id={ch.race_id!r} not found in the races roster. "
                f"Valid ids: {sorted(race_ids)}"
            )
        for sid in ch.learned_skill_ids:
            if sid not in skill_ids:
                raise EntityWriterError(
                    f"character {ch.id} learned_skill_id={sid!r} not found in the skills roster. "
                    f"Valid ids: {sorted(skill_ids)}"
                )
        racial_pool = set(race_by_id[ch.race_id].racial_skill_ids)
        for sid in ch.learned_skill_ids:
            if sid in racial_pool:
                raise EntityWriterError(
                    f"character {ch.id} learned_skill_id={sid!r} is already in race={ch.race_id}'s "
                    "racial_skill_ids. Characters auto-inherit their race's racials, so listing the same id "
                    "in `learned` causes a duplicate — pick a different skill id."
                )

    # active subject must start at the start location
    if c.start_subject_id not in char_ids:
        raise EntityWriterError(
            f"start_subject_id={c.start_subject_id!r} not found in the characters roster."
        )
    start_subject_loc = char_by_id[c.start_subject_id].location_id
    if start_subject_loc != s.start_location_id:
        raise EntityWriterError(
            f"start_subject_id={c.start_subject_id!r} has location_id={start_subject_loc!r}, which "
            f"differs from start_location_id={s.start_location_id!r}. "
            "The active subject must start at the start location."
        )

    for it in c.items:
        if it.owner_character_id is not None and it.owner_character_id not in char_ids:
            raise EntityWriterError(
                f"item {it.id} owner_character_id={it.owner_character_id!r} not found in the characters roster."
            )
        if it.owner_location_id is not None and it.owner_location_id not in loc_ids:
            raise EntityWriterError(
                f"item {it.id} owner_location_id={it.owner_location_id!r} not found in the locations roster."
            )
        if it.owner_character_id is not None and it.owner_location_id is not None:
            raise EntityWriterError(
                f"item {it.id} has both owner_character_id and owner_location_id set. "
                "Use exactly one (or leave both empty if for_player_template=true)."
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
    # matching on `role` was too brittle (the LLM writes things like "포식자/
    # 생물/추적자" instead of the dictionary words "짐승/괴수" we'd match on).
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
                f"The following humanoid characters have no owned armor item: {missing_armor}. "
                "Add one item with kind='armor' and owner_character_id set, for each, to the items roster."
            )
        if missing_weapon:
            lines.append(
                f"The following hostile characters have no owned weapon item: {missing_weapon}. "
                "Add one item with kind='weapon' and owner_character_id set, for each, to the items roster."
            )
        raise EntityWriterError("\n".join(lines))


def _check_arc(s: DecomSetup, c: DecomCast, a: DecomArc) -> None:
    """Phase C: quest/chapter graphs + start_quest + opening-chapter rules."""
    char_ids = {ch.id for ch in c.characters}
    item_ids = {it.id for it in c.items}
    loc_ids = {loc.id for loc in s.locations}
    char_by_id = {ch.id: ch for ch in c.characters}

    quest_ids = _check_ids(a.quests, "quest")
    chapter_ids = _check_ids(a.chapters, "chapter")
    if not a.chapters:
        raise EntityWriterError("chapters is empty. At least 1 required.")

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
                f"not found in the {target_kind} roster."
            )
        if q.giver_id not in char_ids:
            raise EntityWriterError(
                f"quest {q.id} giver_id={q.giver_id!r} not found in the characters roster."
            )
        giver = char_by_id[q.giver_id]
        if giver.is_enemy:
            raise EntityWriterError(
                f"quest {q.id} giver_id={q.giver_id!r} is a hostile character (is_enemy=true). "
                "Quest givers must be non-hostile."
            )
        if q.trigger_kind == "character_death":
            target_char = char_by_id.get(q.target_id)
            if target_char is not None and not target_char.is_enemy:
                raise EntityWriterError(
                    f"quest {q.id}'s character_death trigger target_id={q.target_id!r} is a "
                    "non-hostile character. Death triggers may only point at hostile characters (is_enemy=true) "
                    "(non-hostile NPCs do not die in normal play, so the quest would stay incomplete forever)."
                )

    # Quest prerequisite_ids — must point inside quests, no self-loop, no cycles.
    quest_by_id = {q.id: q for q in a.quests}
    for q in a.quests:
        seen_pid: set[str] = set()
        for pid in q.prerequisite_ids:
            if pid == q.id:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids points at itself. Self-loops are forbidden."
                )
            if pid in seen_pid:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids has duplicate entry {pid!r}."
                )
            seen_pid.add(pid)
            if pid not in quest_ids:
                raise EntityWriterError(
                    f"quest {q.id} prerequisite_ids entry {pid!r} not found in the quests roster."
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
                    f"chapter {ch.id} quest_ids entry {qid!r} not found in the quests roster."
                )
            if qid in quest_to_chapter:
                raise EntityWriterError(
                    f"quest {qid!r} appears in two chapters ({quest_to_chapter[qid]}, {ch.id}). "
                    "A quest must belong to exactly one chapter."
                )
            quest_to_chapter[qid] = ch.id
    unassigned = sorted(quest_ids - quest_to_chapter.keys())
    if unassigned:
        raise EntityWriterError(
            f"quests {unassigned} are not in any chapter. "
            "Distribute every quest across the chapters' quest_ids without omission."
        )

    # Chapter prerequisite_ids — same shape as quest, plus opening-chapter rule.
    for ch in a.chapters:
        seen_pid = set()
        for pid in ch.prerequisite_ids:
            if pid == ch.id:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids points at itself. Self-loops are forbidden."
                )
            if pid in seen_pid:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids has duplicate entry {pid!r}."
                )
            seen_pid.add(pid)
            if pid not in chapter_ids:
                raise EntityWriterError(
                    f"chapter {ch.id} prerequisite_ids entry {pid!r} not found in the chapters roster."
                )
    _check_no_cycle(
        nodes=chapter_ids,
        edges={ch.id: list(ch.prerequisite_ids) for ch in a.chapters},
        kind="chapter",
    )

    if a.start_quest_id not in quest_ids:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} not found in the quests roster."
        )
    opening_chapter_id = quest_to_chapter[a.start_quest_id]
    opening_chapter = next(ch for ch in a.chapters if ch.id == opening_chapter_id)
    if opening_chapter.prerequisite_ids:
        raise EntityWriterError(
            f"chapter {opening_chapter.id} owns start_quest_id={a.start_quest_id!r} but "
            f"prerequisite_ids={opening_chapter.prerequisite_ids} is non-empty. "
            "The opening chapter must have no prereqs (it has to enter active at game start)."
        )

    start_q = quest_by_id[a.start_quest_id]
    if start_q.prerequisite_ids:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} has prerequisite_ids={start_q.prerequisite_ids} non-empty. "
            "The start quest must have no prereqs."
        )
    if not start_q.required:
        raise EntityWriterError(
            f"start_quest_id={a.start_quest_id!r} has required=false. The start quest must be "
            "required=true (so it counts toward chapter progress and ch1 can complete normally)."
        )
    for qid in opening_chapter.quest_ids:
        if qid == a.start_quest_id:
            continue
        if not quest_by_id[qid].prerequisite_ids:
            raise EntityWriterError(
                f"quest {qid!r} sits inside the opening chapter ({opening_chapter.id}) but has empty "
                "prerequisite_ids. Non-start quests in the opening chapter must unlock organically through "
                "prereqs during play (they must not all show as active from game start)."
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


