from typing import Any


SeedRecords = dict[str, dict[str, Any]]


_RECOMMENDED_FIELDS = {
    "location": ("mood", "traits"),
    "item": ("traits",),
    "character": ("mbti", "traits"),
}
_SUPPORT_ACTIONS = {"attack", "defend", "flee", "social"}
_EFFECT_TEMPLATES = {
    "dc_down",
    "extra_heart_damage",
    "prevent_heart_loss",
    "escape_boost",
}


def seed_violations(
    *,
    races: SeedRecords,
    locations: SeedRecords,
    items: SeedRecords,
    skills: SeedRecords,
    npcs: SeedRecords,
    quests: SeedRecords,
    chapters: SeedRecords,
    start: dict[str, Any],
    support_effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
) -> list[str]:
    out: list[str] = []
    _check_key_id("race", races, out)
    _check_key_id("location", locations, out)
    _check_key_id("item", items, out)
    _check_key_id("skill", skills, out)
    if support_effects:
        _check_key_id("support_effect", support_effects, out)
    if statuses:
        _check_key_id("status", statuses, out)
    if factions:
        _check_key_id("faction", factions, out)
    if actions:
        _check_key_id("action", actions, out)
    if knowledge:
        _check_key_id("knowledge", knowledge, out)
    if dialogue_styles:
        _check_key_id("dialogue_style", dialogue_styles, out)
    if mbti:
        _check_key_id("mbti", mbti, out)
    _check_key_id("character", npcs, out)
    _check_key_id("quest", quests, out)
    _check_key_id("chapter", chapters, out)

    start_location_id = start.get("start_location_id")
    if not isinstance(start_location_id, str) or start_location_id not in locations:
        out.append("start_location_id must reference an existing location")
    active_subject_id = start.get("active_subject_id")
    if active_subject_id is not None and active_subject_id not in npcs:
        out.append("active_subject_id must reference an existing character")
    active_quest_id = start.get("active_quest_id")
    if active_quest_id is not None and active_quest_id not in quests:
        out.append("active_quest_id must reference an existing quest")

    for location_id, location in locations.items():
        _check_knowledge_references(
            "location", location_id, location.get("knowledge_ids"), knowledge, out
        )
        for item_id in _str_list(location.get("item_ids")):
            if item_id not in items:
                out.append(f"location {location_id} item_id={item_id!r} not found")
        for connection in _dict_list(location.get("connections")):
            target_id = connection.get("target_id")
            if target_id not in locations:
                out.append(
                    f"location {location_id} connection target_id={target_id!r} not found"
                )

    for item_id, item in items.items():
        _check_support_action(
            "item", item_id, "support_action", item.get("support_action"), out
        )
        _check_effect_template(
            "item", item_id, item.get("effect_template"), support_effects, out
        )
        _check_status_references("item", item_id, item.get("status_ids"), statuses, out)
        _check_knowledge_references(
            "item", item_id, item.get("knowledge_ids"), knowledge, out
        )

    for skill_id, skill in skills.items():
        action_id = skill.get("action_id")
        if action_id is None:
            out.append(f"skill {skill_id} action_id is required")
            continue
        _check_support_action("skill", skill_id, "action_id", action_id, out)
        if (
            action_id is not None
            and actions
            and isinstance(action_id, str)
            and action_id in _SUPPORT_ACTIONS
            and action_id not in actions
        ):
            out.append(f"skill {skill_id} action_id={action_id!r} not found")

    for character_id, character in npcs.items():
        race_id = character.get("race_id")
        if race_id not in races:
            out.append(f"character {character_id} race_id={race_id!r} not found")
        location_id = character.get("location_id")
        if location_id is not None and location_id not in locations:
            out.append(
                f"character {character_id} location_id={location_id!r} not found"
            )
        faction_id = character.get("faction_id")
        if faction_id is not None and (
            not isinstance(faction_id, str)
            or not factions
            or faction_id not in factions
        ):
            out.append(f"character {character_id} faction_id={faction_id!r} not found")
        dialogue_style_id = character.get("dialogue_style_id")
        if dialogue_style_id is not None and (
            not isinstance(dialogue_style_id, str)
            or not dialogue_styles
            or dialogue_style_id not in dialogue_styles
        ):
            out.append(
                f"character {character_id} dialogue_style_id={dialogue_style_id!r} "
                "not found"
            )
        mbti_id = character.get("mbti")
        if mbti_id is not None and (
            not isinstance(mbti_id, str) or not mbti or mbti_id not in mbti
        ):
            out.append(f"character {character_id} mbti={mbti_id!r} not found")
        _check_knowledge_references(
            "character",
            character_id,
            character.get("knowledge_ids"),
            knowledge,
            out,
        )
        for item_id in _str_list(character.get("inventory_ids")):
            if item_id not in items:
                out.append(
                    f"character {character_id} inventory item={item_id!r} not found"
                )
        for slot, item_id in _mapping(character.get("equipment")).items():
            if isinstance(item_id, str) and item_id and item_id not in items:
                out.append(
                    f"character {character_id} equipment.{slot}={item_id!r} not found"
                )
        for skill_id in _str_list(character.get("learned_skill_ids")):
            if skill_id not in skills:
                out.append(f"character {character_id} skill_id={skill_id!r} not found")

    for race_id, race in races.items():
        for skill_id in _str_list(race.get("racial_skill_ids")):
            if skill_id not in skills:
                out.append(f"race {race_id} racial_skill_id={skill_id!r} not found")

    for quest_id, quest in quests.items():
        giver_id = quest.get("giver_id")
        if giver_id is not None and giver_id not in npcs:
            out.append(f"quest {quest_id} giver_id={giver_id!r} not found")
        for trigger in [
            *_dict_list(quest.get("triggers")),
            *_dict_list(quest.get("fail_triggers")),
        ]:
            _check_trigger_target(quest_id, trigger, locations, items, npcs, out)
        for item_id in _str_list(_mapping(quest.get("rewards")).get("items")):
            if item_id not in items:
                out.append(f"quest {quest_id} reward item={item_id!r} not found")
        for prereq_id in _str_list(quest.get("prerequisite_ids")):
            if prereq_id not in quests:
                out.append(f"quest {quest_id} prerequisite_id={prereq_id!r} not found")

    for chapter_id, chapter in chapters.items():
        for quest_id in _str_list(chapter.get("quest_ids")):
            if quest_id not in quests:
                out.append(f"chapter {chapter_id} quest_id={quest_id!r} not found")
        for prereq_id in _str_list(chapter.get("prerequisite_ids")):
            if prereq_id not in chapters:
                out.append(
                    f"chapter {chapter_id} prerequisite_id={prereq_id!r} not found"
                )

    for faction_id, faction in (factions or {}).items():
        for target_id in _mapping(faction.get("relations")):
            if target_id not in (factions or {}):
                out.append(
                    f"faction {faction_id} relation target={target_id!r} not found"
                )

    return out


def seed_warnings(
    *,
    races: SeedRecords,
    locations: SeedRecords,
    items: SeedRecords,
    skills: SeedRecords,
    npcs: SeedRecords,
    quests: SeedRecords,
    chapters: SeedRecords,
    start: dict[str, Any],
    support_effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
) -> list[str]:
    del (
        races,
        skills,
        support_effects,
        statuses,
        factions,
        actions,
        knowledge,
        dialogue_styles,
        mbti,
        quests,
        chapters,
        start,
    )
    out: list[str] = []
    _check_recommended_fields("location", locations, out)
    _check_recommended_fields("item", items, out)
    _check_recommended_fields("character", npcs, out)
    return out


def _check_key_id(kind: str, records: SeedRecords, out: list[str]) -> None:
    for key, record in records.items():
        if record.get("id") != key:
            out.append(f"{kind} key/id mismatch: {key}")


def _check_support_action(
    kind: str,
    record_id: str,
    field: str,
    value: object,
    out: list[str],
) -> None:
    if value is None:
        return
    if value not in _SUPPORT_ACTIONS:
        out.append(f"{kind} {record_id} {field}={value!r} unknown")


def _check_effect_template(
    kind: str,
    record_id: str,
    value: object,
    support_effects: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    if support_effects:
        if value not in support_effects:
            out.append(
                f"{kind} {record_id} effect_template={value!r} "
                "not found in support_effects"
            )
        return
    if value not in _EFFECT_TEMPLATES:
        out.append(f"{kind} {record_id} effect_template={value!r} unknown")


def _check_status_references(
    kind: str,
    record_id: str,
    value: object,
    statuses: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    status_ids = _str_list(value)
    if not statuses:
        for status_id in status_ids:
            out.append(
                f"{kind} {record_id} status_id={status_id!r} "
                "not found in statuses"
            )
        return
    for status_id in status_ids:
        if status_id not in statuses:
            out.append(
                f"{kind} {record_id} status_id={status_id!r} "
                "not found in statuses"
            )


def _check_knowledge_references(
    kind: str,
    record_id: str,
    value: object,
    knowledge: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    for knowledge_id in _str_list(value):
        if not knowledge or knowledge_id not in knowledge:
            out.append(
                f"{kind} {record_id} knowledge_id={knowledge_id!r} not found"
            )


def _check_recommended_fields(
    kind: str,
    records: SeedRecords,
    out: list[str],
) -> None:
    for record_id, record in records.items():
        for field in _RECOMMENDED_FIELDS[kind]:
            if _has_recommended_value(record.get(field)):
                continue
            out.append(f"{kind} {record_id} missing recommended field: {field}")


def _has_recommended_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(isinstance(item, str) and item.strip() for item in value)
    return value is not None


def _check_trigger_target(
    quest_id: str,
    trigger: dict[str, Any],
    locations: SeedRecords,
    items: SeedRecords,
    npcs: SeedRecords,
    out: list[str],
) -> None:
    target_type = trigger.get("type")
    target_id = trigger.get("target_id")
    pools = {
        "location_enter": locations,
        "item_use": items,
        "item_obtained": items,
        "character_death": npcs,
        "character_defeat": npcs,
        "social_check": npcs,
    }
    pool = pools.get(target_type)
    if pool is None:
        out.append(f"quest {quest_id} trigger type={target_type!r} unknown")
        return
    if target_id not in pool:
        out.append(f"quest {quest_id} trigger target_id={target_id!r} not found")


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
