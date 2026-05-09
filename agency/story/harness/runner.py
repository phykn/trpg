"""Entity check helpers + spec metadata.

`SPECS` maps entity kinds to their Pydantic model + cross-ref validator,
used by `agency.story.tool check-entity`. Entity-level rules (stat
invariants, HP/MP formula, NPC seed extras) live in `src.game.engines.invariants`.
The LLM-call writer that originally consumed this metadata has been removed —
Claude Code now writes entities directly per agency/story/SKILL.md.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from src.game.domain.entities import (
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from src.game.engines.invariants import (
    check_character,
    check_item,
    check_seed_character,
)

from ._common import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
)

# --- types & errors --------------------------------------------------------


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


# --- manifest cross-ref checks --------------------------------------------


def _check_location_refs(loc: Location, refs: dict[str, set[str]]) -> None:
    location_ids = refs.get("location", set())
    item_ids = refs.get("item", set())
    for c in loc.connections:
        if c.target_id == loc.id:
            raise EntityWriterError(
                f"location.connections points at itself ({loc.id})."
            )
        if c.target_id not in location_ids:
            raise EntityWriterError(
                f"location.connections.target_id={c.target_id!r} not found in scenario locations. "
                f"Valid ids: {sorted(location_ids)}"
            )
    for iid in loc.item_ids:
        if iid not in item_ids:
            raise EntityWriterError(
                f"location.item_ids entry {iid!r} not found in scenario items."
            )


def _check_character_refs(ch: Character, refs: dict[str, set[str]]) -> None:
    """Manifest cross-ref only — race_id/location_id/skill_ids pool checks."""
    races = refs.get("race", set())
    if ch.race_id not in races:
        raise EntityWriterError(
            f"character.race_id={ch.race_id!r} not found in scenario races. "
            f"Valid ids: {sorted(races)}"
        )
    locations = refs.get("location", set())
    if ch.location_id is not None and ch.location_id not in locations:
        raise EntityWriterError(
            f"character.location_id={ch.location_id!r} not found in scenario locations. "
            f"Valid ids: {sorted(locations)}"
        )
    skills = refs.get("skill", set())
    for sid in (*ch.racial_skill_ids, *ch.learned_skill_ids):
        if sid not in skills:
            raise EntityWriterError(
                f"character.skill_id={sid!r} not found in scenario skills. "
                "Create that skill first."
            )


def _check_race_refs(r: Race, refs: dict[str, set[str]]) -> None:
    skills = refs.get("skill", set())
    for sid in r.racial_skill_ids:
        if sid not in skills:
            raise EntityWriterError(
                f"race.racial_skill_id={sid!r} not found in scenario skills."
            )


def _check_quest_refs(q: Quest, refs: dict[str, set[str]]) -> None:
    characters = refs.get("character", set())
    if q.giver_id not in characters:
        raise EntityWriterError(
            f"quest.giver_id={q.giver_id!r} not found in scenario characters."
        )
    for t in [*q.triggers, *q.fail_triggers]:
        target_kind = TRIGGER_TARGET_KIND.get(t.type)
        if target_kind is None:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) type={t.type!r} unknown. "
                f"Valid values: {sorted(TRIGGER_TARGET_KIND)}"
            )
        pool = refs.get(target_kind, set())
        if t.target_id not in pool:
            raise EntityWriterError(
                f"quest trigger (id={t.id}) target_id={t.target_id!r} not found in the "
                f"{target_kind} pool."
            )
    quests = refs.get("quest", set())
    for pid in q.prerequisite_ids:
        if pid not in quests:
            raise EntityWriterError(
                f"quest.prerequisite_ids entry {pid!r} not found in scenario quests."
            )


def _check_chapter_refs(ch: Chapter, refs: dict[str, set[str]]) -> None:
    quests = refs.get("quest", set())
    for qid in ch.quest_ids:
        if qid not in quests:
            raise EntityWriterError(
                f"chapter.quest_ids entry {qid!r} not found in scenario quests."
            )


# --- spec table ------------------------------------------------------------

SPECS: dict[str, EntitySpec] = {
    "race": EntitySpec(
        kind="race",
        model=Race,
        sub_dir="races",
        fragment="race.md",
        ref_kinds=("skill",),
        check_refs=_check_race_refs,
    ),
    "location": EntitySpec(
        kind="location",
        model=Location,
        sub_dir="locations",
        fragment="location.md",
        ref_kinds=("location", "item"),
        check_refs=_check_location_refs,
    ),
    "skill": EntitySpec(
        kind="skill",
        model=Skill,
        sub_dir="skills",
        fragment="skill.md",
    ),
    "item": EntitySpec(
        kind="item",
        model=Item,
        sub_dir="items",
        fragment="item.md",
    ),
    "character": EntitySpec(
        kind="character",
        model=Character,
        sub_dir="characters",
        fragment="character.md",
        ref_kinds=("race", "location", "item", "skill"),
        check_refs=_check_character_refs,
    ),
    "quest": EntitySpec(
        kind="quest",
        model=Quest,
        sub_dir="quests",
        fragment="quest.md",
        ref_kinds=("character", "location", "item", "quest"),
        check_refs=_check_quest_refs,
    ),
    "chapter": EntitySpec(
        kind="chapter",
        model=Chapter,
        sub_dir="chapters",
        fragment="chapter.md",
        ref_kinds=("quest",),
        check_refs=_check_chapter_refs,
    ),
}


# --- build helpers ---------------------------------------------------------


def _load_dir(scenario_dir: Path, sub_dir: str) -> list[dict]:
    d = scenario_dir / sub_dir
    if not d.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def _collect_refs(scenario_dir: Path, spec: EntitySpec) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {
        spec.kind: {e["id"] for e in _load_dir(scenario_dir, spec.sub_dir)}
    }
    for rk in spec.ref_kinds:
        if rk == spec.kind:
            continue
        refs[rk] = {e["id"] for e in _load_dir(scenario_dir, SPECS[rk].sub_dir)}
    return refs


def _items_pool(scenario_dir: Path) -> dict[str, Item]:
    return {e["id"]: Item.model_validate(e) for e in _load_dir(scenario_dir, "items")}


def _skills_pool(scenario_dir: Path) -> dict[str, Skill]:
    return {e["id"]: Skill.model_validate(e) for e in _load_dir(scenario_dir, "skills")}


def _check_entity_invariants(
    entity: BaseModel, scenario_dir: Path, *, skeleton: bool = False
) -> None:
    """Dispatch to src.game.engines.invariants — all entity-level rules.

    Cross-ref between manifests is already done by spec.check_refs above; this
    runs the rule layer (stat invariants, HP/MP formula, NPC seed extras, etc).

    skeleton=True: only stateless rules (pair-trade, HP/MP formula). The
    items/skills pool isn't yet on disk, and character.inventory_ids /
    skill_ids are intentionally empty — pool-based checks would false-fire.
    """
    if isinstance(entity, Character):
        if skeleton:
            violations = check_character(entity)
        else:
            violations = check_seed_character(
                entity, _items_pool(scenario_dir), _skills_pool(scenario_dir)
            )
    elif isinstance(entity, Item):
        violations = check_item(entity)
    else:
        return
    if violations:
        raise EntityWriterError("invariant violation:\n" + "\n".join(violations))


def _check_id(
    entity: BaseModel, existing: set[str], force_id: str | None = None
) -> None:
    eid: str = entity.id  # type: ignore[attr-defined]
    if not ID_PATTERN.match(eid):
        raise EntityWriterError(
            f"id={eid!r} does not match the required pattern. ASCII snake_case ([a-z][a-z0-9_]{{1,30}}) required."
        )
    if force_id is not None and eid != force_id:
        raise EntityWriterError(
            f"id={eid!r} differs from the forced id={force_id!r}. "
            "Follow the hint's id directive exactly — do not change a single character."
        )
    if eid in existing:
        raise EntityWriterError(
            f"id={eid!r} collides with existing ids. Existing: {sorted(existing)}"
        )
