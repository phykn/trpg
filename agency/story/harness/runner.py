"""Raw scenario record checks for `agency.story.tool check-entity`."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._common import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
)


Record = dict[str, Any]


def _noop_check(entity: Record, refs: dict[str, set[str]]) -> None:
    return None


@dataclass(frozen=True)
class EntitySpec:
    kind: str
    sub_dir: str
    ref_kinds: tuple[str, ...] = ()
    check_refs: Callable[[Record, dict[str, set[str]]], None] = field(
        default=_noop_check
    )


def _check_location_refs(loc: Record, refs: dict[str, set[str]]) -> None:
    location_ids = refs.get("location", set())
    item_ids = refs.get("item", set())
    loc_id = _entity_id(loc)
    for connection in _dict_list(loc.get("connections")):
        target_id = connection.get("target_id")
        if target_id == loc_id:
            raise EntityWriterError(
                f"location.connections points at itself ({loc_id})."
            )
        if target_id not in location_ids:
            raise EntityWriterError(
                f"location.connections.target_id={target_id!r} not found in scenario locations. "
                f"Valid ids: {sorted(location_ids)}"
            )
    for item_id in _str_list(loc.get("item_ids")):
        if item_id not in item_ids:
            raise EntityWriterError(
                f"location.item_ids entry {item_id!r} not found in scenario items."
            )


def _check_character_refs(character: Record, refs: dict[str, set[str]]) -> None:
    races = refs.get("race", set())
    race_id = character.get("race_id")
    if race_id not in races:
        raise EntityWriterError(
            f"character.race_id={race_id!r} not found in scenario races. "
            f"Valid ids: {sorted(races)}"
        )
    locations = refs.get("location", set())
    location_id = character.get("location_id")
    if location_id is not None and location_id not in locations:
        raise EntityWriterError(
            f"character.location_id={location_id!r} not found in scenario locations. "
            f"Valid ids: {sorted(locations)}"
        )
    skills = refs.get("skill", set())
    for skill_id in _str_list(character.get("learned_skill_ids")):
        if skill_id not in skills:
            raise EntityWriterError(
                f"character.skill_id={skill_id!r} not found in scenario skills. "
                "Create that skill first."
            )


def _check_race_refs(race: Record, refs: dict[str, set[str]]) -> None:
    skills = refs.get("skill", set())
    for skill_id in _str_list(race.get("racial_skill_ids")):
        if skill_id not in skills:
            raise EntityWriterError(
                f"race.racial_skill_id={skill_id!r} not found in scenario skills."
            )


def _check_quest_refs(quest: Record, refs: dict[str, set[str]]) -> None:
    characters = refs.get("character", set())
    giver_id = quest.get("giver_id")
    if giver_id is not None and giver_id not in characters:
        raise EntityWriterError(
            f"quest.giver_id={giver_id!r} not found in scenario characters."
        )
    for trigger in [
        *_dict_list(quest.get("triggers")),
        *_dict_list(quest.get("fail_triggers")),
    ]:
        target_kind = TRIGGER_TARGET_KIND.get(trigger.get("type"))
        if target_kind is None:
            raise EntityWriterError(
                f"quest trigger (id={trigger.get('id')}) type={trigger.get('type')!r} unknown. "
                f"Valid values: {sorted(TRIGGER_TARGET_KIND)}"
            )
        pool = refs.get(target_kind, set())
        target_id = trigger.get("target_id")
        if target_id not in pool:
            raise EntityWriterError(
                f"quest trigger (id={trigger.get('id')}) target_id={target_id!r} not found in the "
                f"{target_kind} pool."
            )
    quests = refs.get("quest", set())
    for prereq_id in _str_list(quest.get("prerequisite_ids")):
        if prereq_id not in quests:
            raise EntityWriterError(
                f"quest.prerequisite_ids entry {prereq_id!r} not found in scenario quests."
            )


def _check_chapter_refs(chapter: Record, refs: dict[str, set[str]]) -> None:
    quests = refs.get("quest", set())
    for quest_id in _str_list(chapter.get("quest_ids")):
        if quest_id not in quests:
            raise EntityWriterError(
                f"chapter.quest_ids entry {quest_id!r} not found in scenario quests."
            )


SPECS: dict[str, EntitySpec] = {
    "race": EntitySpec(
        kind="race",
        sub_dir="races",
        ref_kinds=("skill",),
        check_refs=_check_race_refs,
    ),
    "location": EntitySpec(
        kind="location",
        sub_dir="locations",
        ref_kinds=("location", "item"),
        check_refs=_check_location_refs,
    ),
    "skill": EntitySpec(kind="skill", sub_dir="skills"),
    "item": EntitySpec(kind="item", sub_dir="items"),
    "character": EntitySpec(
        kind="character",
        sub_dir="characters",
        ref_kinds=("race", "location", "item", "skill"),
        check_refs=_check_character_refs,
    ),
    "quest": EntitySpec(
        kind="quest",
        sub_dir="quests",
        ref_kinds=("character", "location", "item", "quest"),
        check_refs=_check_quest_refs,
    ),
    "chapter": EntitySpec(
        kind="chapter",
        sub_dir="chapters",
        ref_kinds=("quest",),
        check_refs=_check_chapter_refs,
    ),
}


def _load_dir(scenario_dir: Path, sub_dir: str) -> list[Record]:
    dir_path = scenario_dir / sub_dir
    if not dir_path.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(dir_path.glob("*.json"))
    ]


def _collect_refs(scenario_dir: Path, spec: EntitySpec) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {
        spec.kind: {
            _entity_id(entity) for entity in _load_dir(scenario_dir, spec.sub_dir)
        }
    }
    for ref_kind in spec.ref_kinds:
        if ref_kind == spec.kind:
            continue
        refs[ref_kind] = {
            _entity_id(entity)
            for entity in _load_dir(scenario_dir, SPECS[ref_kind].sub_dir)
        }
    return refs


def _check_entity_invariants(
    entity: Record, scenario_dir: Path, *, skeleton: bool = False
) -> None:
    kind = _guess_kind(entity)
    if kind == "skill":
        primary_stat = entity.get("primary_stat")
        if primary_stat not in {"body", "agility", "mind", "presence"}:
            raise EntityWriterError(
                f"skill.primary_stat={primary_stat!r} must be one of body/agility/mind/presence."
            )
        return
    if kind == "character":
        _check_graph_stats(entity)
        if not skeleton:
            _check_character_pools(entity, scenario_dir)
        return
    if kind == "item":
        effect = entity.get("effects")
        if isinstance(effect, dict) and effect.get("type") not in {
            "weapon",
            "armor",
            "consumable",
        }:
            raise EntityWriterError(
                f"item.effects.type={effect.get('type')!r} unknown."
            )


def _check_id(entity: Record, existing: set[str], force_id: str | None = None) -> None:
    entity_id = _entity_id(entity)
    if not ID_PATTERN.match(entity_id):
        raise EntityWriterError(
            f"id={entity_id!r} does not match the required pattern. ASCII snake_case ([a-z][a-z0-9_]{{1,30}}) required."
        )
    if force_id is not None and entity_id != force_id:
        raise EntityWriterError(
            f"id={entity_id!r} differs from the forced id={force_id!r}. "
            "Follow the hint's id directive exactly."
        )
    if entity_id in existing:
        raise EntityWriterError(
            f"id={entity_id!r} collides with existing ids. Existing: {sorted(existing)}"
        )


def _check_graph_stats(entity: Record) -> None:
    stats = entity.get("stats")
    if stats is None:
        return
    if not isinstance(stats, dict):
        raise EntityWriterError("character.stats must be an object.")
    missing = {"body", "agility", "mind", "presence"} - stats.keys()
    if missing:
        raise EntityWriterError(
            f"character.stats missing graph stat keys: {sorted(missing)}"
        )


def _check_character_pools(entity: Record, scenario_dir: Path) -> None:
    items = {_entity_id(item) for item in _load_dir(scenario_dir, "items")}
    skills = {_entity_id(skill) for skill in _load_dir(scenario_dir, "skills")}
    for item_id in _str_list(entity.get("inventory_ids")):
        if item_id not in items:
            raise EntityWriterError(
                f"character.inventory_ids entry {item_id!r} missing."
            )
    for item_id in _mapping(entity.get("equipment")).values():
        if isinstance(item_id, str) and item_id and item_id not in items:
            raise EntityWriterError(f"character.equipment item {item_id!r} missing.")
    for skill_id in _str_list(entity.get("learned_skill_ids")):
        if skill_id not in skills:
            raise EntityWriterError(f"character.skill_id {skill_id!r} missing.")


def _guess_kind(entity: Record) -> str:
    if "primary_stat" in entity:
        return "skill"
    if "race_id" in entity and "location_id" in entity:
        return "character"
    if "effects" in entity and "weight" in entity:
        return "item"
    return "unknown"


def _entity_id(entity: Record) -> str:
    value = entity.get("id")
    if not isinstance(value, str) or not value:
        raise EntityWriterError("entity requires a non-empty id.")
    return value


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[Record]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
