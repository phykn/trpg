from typing import Any


SeedRecords = dict[str, dict[str, Any]]


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
) -> list[str]:
    out: list[str] = []
    _check_key_id("race", races, out)
    _check_key_id("location", locations, out)
    _check_key_id("item", items, out)
    _check_key_id("skill", skills, out)
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
        for item_id in _str_list(location.get("item_ids")):
            if item_id not in items:
                out.append(f"location {location_id} item_id={item_id!r} not found")
        for connection in _dict_list(location.get("connections")):
            target_id = connection.get("target_id")
            if target_id not in locations:
                out.append(
                    f"location {location_id} connection target_id={target_id!r} not found"
                )

    for character_id, character in npcs.items():
        race_id = character.get("race_id")
        if race_id not in races:
            out.append(f"character {character_id} race_id={race_id!r} not found")
        location_id = character.get("location_id")
        if location_id is not None and location_id not in locations:
            out.append(
                f"character {character_id} location_id={location_id!r} not found"
            )
        for item_id in _str_list(character.get("inventory_ids")):
            if item_id not in items:
                out.append(f"character {character_id} inventory item={item_id!r} not found")
        for slot, item_id in _mapping(character.get("equipment")).items():
            if isinstance(item_id, str) and item_id and item_id not in items:
                out.append(
                    f"character {character_id} equipment.{slot}={item_id!r} not found"
                )
        for skill_id in [
            *_str_list(character.get("racial_skill_ids")),
            *_str_list(character.get("learned_skill_ids")),
        ]:
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

    return out


def _check_key_id(kind: str, records: SeedRecords, out: list[str]) -> None:
    for key, record in records.items():
        if record.get("id") != key:
            out.append(f"{kind} key/id mismatch: {key}")


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
        "character_death": npcs,
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
