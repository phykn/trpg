"""Raw scenario record checks for `agency.story.tool check-entity`."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import (
    ID_PATTERN,
    TRIGGER_TARGET_KIND,
    EntityWriterError,
)
from src.game.seed.validation import (  # noqa: E402
    _EFFECT_TEMPLATES,
    _FORBIDDEN_SEED_KEYS,
    _LEGACY_KEY_RENAMES,
    _SUPPORT_ACTIONS,
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
        target = connection.get("target")
        if target == loc_id:
            raise EntityWriterError(
                f"location.connections points at itself ({loc_id})."
            )
        if target not in location_ids:
            raise EntityWriterError(
                f"location.connections.target={target!r} not found in scenario locations. "
                f"Valid ids: {sorted(location_ids)}"
            )
    for item_id in _str_list(loc.get("items")):
        if item_id not in item_ids:
            raise EntityWriterError(
                f"location.items entry {item_id!r} not found in scenario items."
            )


def _check_character_refs(character: Record, refs: dict[str, set[str]]) -> None:
    races = refs.get("race", set())
    race_id = character.get("race")
    if race_id not in races:
        raise EntityWriterError(
            f"character.race={race_id!r} not found in scenario races. "
            f"Valid ids: {sorted(races)}"
        )
    locations = refs.get("location", set())
    location_id = character.get("location")
    if location_id is not None and location_id not in locations:
        raise EntityWriterError(
            f"character.location={location_id!r} not found in scenario locations. "
            f"Valid ids: {sorted(locations)}"
        )
    skills = refs.get("skill", set())
    for skill_id in _str_list(character.get("learned_skills")):
        if skill_id not in skills:
            raise EntityWriterError(
                f"character.skill={skill_id!r} not found in scenario skills. "
                "Create that skill first."
            )


def _check_race_refs(race: Record, refs: dict[str, set[str]]) -> None:
    skills = refs.get("skill", set())
    for skill_id in _str_list(race.get("racial_skills")):
        if skill_id not in skills:
            raise EntityWriterError(
                f"race.racial_skills={skill_id!r} not found in scenario skills."
            )


def _check_quest_refs(quest: Record, refs: dict[str, set[str]]) -> None:
    characters = refs.get("character", set())
    giver_id = quest.get("giver")
    if giver_id is not None and giver_id not in characters:
        raise EntityWriterError(
            f"quest.giver={giver_id!r} not found in scenario characters."
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
        target = trigger.get("target")
        if target not in pool:
            raise EntityWriterError(
                f"quest trigger (id={trigger.get('id')}) target={target!r} not found in the "
                f"{target_kind} pool."
            )
    quests = refs.get("quest", set())
    for prereq_id in _str_list(quest.get("prerequisites")):
        if prereq_id not in quests:
            raise EntityWriterError(
                f"quest.prerequisites entry {prereq_id!r} not found in scenario quests."
            )
    items = refs.get("item", set())
    for item_id in _str_list(_mapping(quest.get("rewards")).get("items")):
        if item_id not in items:
            raise EntityWriterError(
                f"quest.rewards.items entry {item_id!r} not found in scenario items."
            )
    for choice_id, choice in _mapping(quest.get("choices")).items():
        if not isinstance(choice, dict):
            raise EntityWriterError(
                f"quest.choices entry {choice_id!r} must be an object."
            )
        for item_id in _str_list(_mapping(choice.get("rewards")).get("items")):
            if item_id not in items:
                raise EntityWriterError(
                    f"quest.choices.{choice_id}.rewards.items entry {item_id!r} "
                    "not found in scenario items."
                )


def _check_chapter_refs(chapter: Record, refs: dict[str, set[str]]) -> None:
    quests = refs.get("quest", set())
    for quest_id in _str_list(chapter.get("quests")):
        if quest_id not in quests:
            raise EntityWriterError(
                f"chapter.quests entry {quest_id!r} not found in scenario quests."
            )
    chapters = refs.get("chapter", set())
    for prereq_id in _str_list(chapter.get("prerequisites")):
        if prereq_id not in chapters:
            raise EntityWriterError(
                f"chapter.prerequisites entry {prereq_id!r} not found in scenario chapters."
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
    aggregate_path = scenario_dir / f"{sub_dir}.json"
    if aggregate_path.is_file():
        value = json.loads(aggregate_path.read_text(encoding="utf-8"))
        return list(_records_from_json(value).values())
    dir_path = scenario_dir / sub_dir
    if not dir_path.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(dir_path.glob("*.json"))
    ]


def _records_from_json(value: object) -> dict[str, Record]:
    if isinstance(value, dict):
        candidates = value.values()
    elif isinstance(value, list):
        candidates = value
    else:
        return {}
    records: dict[str, Record] = {}
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        record_id = obj.get("id")
        if isinstance(record_id, str):
            records[record_id] = obj
    return records


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
    entity: Record, scenario_dir: Path, *, kind: str, skeleton: bool = False
) -> None:
    _check_forbidden_seed_shape(entity, kind)
    if kind == "location":
        _check_location_catalog_refs(entity, scenario_dir)
        return
    if kind == "skill":
        action = entity.get("action")
        if action is not None and not isinstance(action, str):
            raise EntityWriterError("skill.action must be an action id string.")
        _check_action_ref("skill", _entity_id(entity), action)
        effect = entity.get("effect")
        if effect is not None and not isinstance(effect, str):
            raise EntityWriterError("skill.effect must be an effect id string.")
        _check_skill_text_quality(entity)
        return
    if kind == "character":
        _check_character_catalog_refs(entity, scenario_dir)
        if not skeleton:
            _check_character_pools(entity, scenario_dir)
        return
    if kind == "item":
        effect = entity.get("effect")
        if effect is not None and not isinstance(effect, str):
            raise EntityWriterError(
                f"item.effect={effect!r} must be an effect id string or null."
            )
        _check_item_catalog_refs(entity, scenario_dir)


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


def _check_character_pools(entity: Record, scenario_dir: Path) -> None:
    items = {_entity_id(item) for item in _load_dir(scenario_dir, "items")}
    skills = {_entity_id(skill) for skill in _load_dir(scenario_dir, "skills")}
    for item_id in _str_list(entity.get("inventory")):
        if item_id not in items:
            raise EntityWriterError(
                f"character.inventory entry {item_id!r} missing."
            )
    for item_id in _mapping(entity.get("equipment")).values():
        if isinstance(item_id, str) and item_id:
            raise EntityWriterError(
                "character.equipment is player-only; keep NPC gear in inventory."
            )
    for skill_id in _str_list(entity.get("learned_skills")):
        if skill_id not in skills:
            raise EntityWriterError(f"character.skill {skill_id!r} missing.")


def _check_forbidden_seed_shape(entity: Record, kind: str) -> None:
    violations: list[str] = []
    _walk_forbidden_seed_shape(entity, f"{kind} {_entity_id(entity)}", violations)
    if violations:
        raise EntityWriterError("\n".join(violations))


def _walk_forbidden_seed_shape(
    value: object,
    path: str,
    violations: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _LEGACY_KEY_RENAMES:
                violations.append(
                    f"{child_path} uses legacy key; use "
                    f"{_LEGACY_KEY_RENAMES[key]!r}"
                )
            elif key in _FORBIDDEN_SEED_KEYS:
                violations.append(f"{child_path} is not allowed in seed data")
            elif key != "id" and (key.endswith("_id") or key.endswith("_ids")):
                violations.append(f"{child_path} uses legacy *_id/*_ids naming")

            if key == "on_use" and child is None:
                violations.append(f"{child_path} must be omitted when empty")
            if key in {"difficulty", "key_item", "required"} and child is None:
                violations.append(f"{child_path} must be omitted when empty")

            _walk_forbidden_seed_shape(child, child_path, violations)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_seed_shape(child, f"{path}[{index}]", violations)


_PLACEHOLDER_SKILL_NAMES = {
    "기본 공격",
    "기본 방어",
    "방어 자세",
    "임기응변",
    "고른 숨",
    "침착한 설득",
    "밀어붙이기",
    "버티는 자세",
}


def skill_text_quality_violations(skill_id: str, skill: Record) -> list[str]:
    name = skill.get("name")
    if isinstance(name, str) and name.strip() in _PLACEHOLDER_SKILL_NAMES:
        return [
            f"skill {skill_id} name={name!r} is a placeholder; write a concrete "
            "scenario-grounded technique name tied to its owner and action."
        ]
    return []


def _check_skill_text_quality(entity: Record) -> None:
    violations = skill_text_quality_violations(_entity_id(entity), entity)
    if violations:
        raise EntityWriterError("\n".join(violations))


def _check_item_catalog_refs(entity: Record, scenario_dir: Path) -> None:
    item_id = _entity_id(entity)
    violations: list[str] = []
    action = entity.get("action")
    if action is not None and action not in _SUPPORT_ACTIONS:
        violations.append(f"item {item_id} action={action!r} unknown")
    effects = _load_catalog_if_present(scenario_dir, "effects")
    effect_id = entity.get("effect")
    if isinstance(effect_id, str):
        if effects is not None and effect_id not in effects:
            violations.append(f"item {item_id} effect={effect_id!r} not found in effects")
        if effects is None and effect_id not in _EFFECT_TEMPLATES:
            violations.append(f"item {item_id} effect={effect_id!r} unknown")
        if (
            effects is not None
            and effects.get(effect_id, {}).get("kind") in {"heal", "mp_restore"}
            and not isinstance(entity.get("amount"), int)
        ):
            violations.append(
                f"item {item_id} amount is required for effect={effect_id!r}"
            )
    _collect_catalog_ref_errors(
        violations, entity, scenario_dir, "item", item_id, "slot", "slots"
    )
    _collect_catalog_list_ref_errors(
        violations, entity, scenario_dir, "item", item_id, "knowledge", "knowledge"
    )
    _raise_catalog_violations(violations)


def _check_character_catalog_refs(entity: Record, scenario_dir: Path) -> None:
    character_id = _entity_id(entity)
    violations: list[str] = []
    _collect_catalog_ref_errors(
        violations, entity, scenario_dir, "character", character_id, "mbti", "mbti"
    )
    _collect_catalog_ref_errors(
        violations,
        entity,
        scenario_dir,
        "character",
        character_id,
        "faction",
        "factions",
    )
    _collect_catalog_ref_errors(
        violations,
        entity,
        scenario_dir,
        "character",
        character_id,
        "dialogue_style",
        "dialogue_styles",
    )
    _collect_catalog_list_ref_errors(
        violations,
        entity,
        scenario_dir,
        "character",
        character_id,
        "knowledge",
        "knowledge",
    )
    _raise_catalog_violations(violations)


def _check_location_catalog_refs(entity: Record, scenario_dir: Path) -> None:
    location_id = _entity_id(entity)
    violations: list[str] = []
    _collect_catalog_list_ref_errors(
        violations,
        entity,
        scenario_dir,
        "location",
        location_id,
        "knowledge",
        "knowledge",
    )
    _raise_catalog_violations(violations)


def _check_action_ref(kind: str, record_id: str, value: object) -> None:
    if value is None:
        return
    if value not in _SUPPORT_ACTIONS:
        raise EntityWriterError(f"{kind} {record_id} action={value!r} unknown")


def _raise_catalog_violations(violations: list[str]) -> None:
    if violations:
        raise EntityWriterError("\n".join(violations))


def _collect_catalog_ref_errors(
    violations: list[str],
    entity: Record,
    scenario_dir: Path,
    kind: str,
    record_id: str,
    field: str,
    catalog_kind: str,
) -> None:
    value = entity.get(field)
    if value is None:
        return
    catalog = _load_catalog_if_present(scenario_dir, catalog_kind)
    if catalog is None:
        return
    if not isinstance(value, str) or value not in catalog:
        violations.append(f"{kind} {record_id} {field}={value!r} not found")


def _collect_catalog_list_ref_errors(
    violations: list[str],
    entity: Record,
    scenario_dir: Path,
    kind: str,
    record_id: str,
    field: str,
    catalog_kind: str,
) -> None:
    value = entity.get(field)
    if value is None:
        return
    catalog = _load_catalog_if_present(scenario_dir, catalog_kind)
    if catalog is None:
        return
    for ref_id in _str_list(value):
        if ref_id not in catalog:
            violations.append(f"{kind} {record_id} {field}_id={ref_id!r} not found")


def _load_catalog_if_present(scenario_dir: Path, kind: str) -> dict[str, Record] | None:
    aggregate_path = scenario_dir / f"{kind}.json"
    if not aggregate_path.is_file():
        return None
    raw = json.loads(aggregate_path.read_text(encoding="utf-8"))
    return _records_from_json(raw)


def _entity_id(entity: Record) -> str:
    value = entity.get("id")
    if not isinstance(value, str) or not value:
        raise EntityWriterError("entity requires a non-empty id.")
    return value


def _records_from_json(value: object) -> dict[str, Record]:
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, dict):
        candidates = list(value.values())
    else:
        return {}
    records: dict[str, Record] = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if isinstance(item_id, str):
            records[item_id] = item
    return records


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
