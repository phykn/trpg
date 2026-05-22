from typing import Any


SeedRecords = dict[str, dict[str, Any]]


_LEGACY_KEY_RENAMES = {
    "action_category_id": "action",
    "action_id": "action",
    "dialogue_style_id": "dialogue_style",
    "effect_template": "effect",
    "faction_id": "faction",
    "giver_id": "giver",
    "inventory_ids": "inventory",
    "item_ids": "items",
    "knowledge_ids": "knowledge",
    "learned_skill_ids": "learned_skills",
    "location_id": "location",
    "prerequisite_ids": "prerequisites",
    "private_hint": "secrets",
    "quest_ids": "quests",
    "race_id": "race",
    "racial_skill_ids": "racial_skills",
    "slot_id": "slot",
    "support_action": "action",
}
_FORBIDDEN_SEED_KEYS = {
    *(_LEGACY_KEY_RENAMES),
    "disposition",
    "hp",
    "job",
    "max_hp",
    "max_mp",
    "mp",
    "stats",
    "status_ids",
    "tags",
    "weather",
}
_RECOMMENDED_FIELDS = {
    "location": ("mood", "traits"),
    "item": ("traits",),
    "character": ("mbti", "traits"),
}
_SUPPORT_ACTIONS = {"attack", "defend", "flee", "talk"}
_EFFECT_TEMPLATES = {
    "heal",
    "mp_restore",
    "dc_down",
    "dc_up",
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
    effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    slots: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
    player: dict[str, Any] | None = None,
) -> list[str]:
    out: list[str] = []
    _check_forbidden_seed_shape(
        records={
            "race": races,
            "location": locations,
            "item": items,
            "skill": skills,
            "effect": effects or {},
            "status": statuses or {},
            "slot": slots or {},
            "faction": factions or {},
            "action": actions or {},
            "knowledge": knowledge or {},
            "dialogue_style": dialogue_styles or {},
            "mbti": mbti or {},
            "character": npcs,
            "quest": quests,
            "chapter": chapters,
        },
        start=start,
        player=player,
        out=out,
    )
    _check_key_id("race", races, out)
    _check_key_id("location", locations, out)
    _check_key_id("item", items, out)
    _check_key_id("skill", skills, out)
    if effects:
        _check_key_id("effect", effects, out)
    if statuses:
        _check_key_id("status", statuses, out)
    if slots:
        _check_key_id("slot", slots, out)
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

    start_location_id = start.get("start_location")
    if not isinstance(start_location_id, str) or start_location_id not in locations:
        out.append("start_location must reference an existing location")
    active_subject_id = start.get("active_subject")
    if active_subject_id is not None and active_subject_id not in npcs:
        out.append("active_subject must reference an existing character")
    active_quest_id = start.get("active_quest")
    if active_quest_id is not None and active_quest_id not in quests:
        out.append("active_quest must reference an existing quest")
    intro_text = start.get("intro_text")
    if intro_text is not None and (
        not isinstance(intro_text, str) or not intro_text.strip()
    ):
        out.append("intro_text must be a non-empty string when present")

    for location_id, location in locations.items():
        _check_knowledge_references(
            "location", location_id, location.get("knowledge"), knowledge, out
        )
        for item_id in _str_list(location.get("items")):
            if item_id not in items:
                out.append(f"location {location_id} item={item_id!r} not found")
        for connection in _dict_list(location.get("connections")):
            target = connection.get("target")
            if target not in locations:
                out.append(
                    f"location {location_id} connection target={target!r} not found"
                )
            required_quest_id = connection.get("requires_quest")
            if required_quest_id is not None and required_quest_id not in quests:
                out.append(
                    f"location {location_id} connection requires_quest="
                    f"{required_quest_id!r} not found"
                )

    for item_id, item in items.items():
        _check_action(
            "item", item_id, "action", item.get("action"), out
        )
        _check_effect(
            "item", item_id, item.get("effect"), effects, out
        )
        _check_item_effect_fields(item_id, item, effects, out)
        slot_id = item.get("slot")
        if slot_id is not None and (
            not isinstance(slot_id, str) or not slots or slot_id not in slots
        ):
            out.append(f"item {item_id} slot={slot_id!r} not found")
        _check_knowledge_references(
            "item", item_id, item.get("knowledge"), knowledge, out
        )

    for skill_id, skill in skills.items():
        action = skill.get("action")
        if action is None:
            out.append(f"skill {skill_id} action is required")
            continue
        _check_action("skill", skill_id, "action", action, out)
        if (
            action is not None
            and actions
            and isinstance(action, str)
            and action in _SUPPORT_ACTIONS
            and action not in actions
        ):
            out.append(f"skill {skill_id} action={action!r} not found")

    for character_id, character in npcs.items():
        race_id = character.get("race")
        if race_id not in races:
            out.append(f"character {character_id} race={race_id!r} not found")
        location_id = character.get("location")
        if location_id is not None and location_id not in locations:
            out.append(
                f"character {character_id} location={location_id!r} not found"
            )
        faction_id = character.get("faction")
        if faction_id is not None and (
            not isinstance(faction_id, str)
            or not factions
            or faction_id not in factions
        ):
            out.append(f"character {character_id} faction={faction_id!r} not found")
        dialogue_style_id = character.get("dialogue_style")
        if dialogue_style_id is not None and (
            not isinstance(dialogue_style_id, str)
            or not dialogue_styles
            or dialogue_style_id not in dialogue_styles
        ):
            out.append(
                f"character {character_id} dialogue_style={dialogue_style_id!r} "
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
            character.get("knowledge"),
            knowledge,
            out,
        )
        for item_id in _str_list(character.get("inventory")):
            if item_id not in items:
                out.append(
                    f"character {character_id} inventory item={item_id!r} not found"
                )
        for slot, item_id in _mapping(character.get("equipment")).items():
            if isinstance(item_id, str) and item_id and item_id not in items:
                out.append(
                    f"character {character_id} equipment.{slot}={item_id!r} not found"
                )
        for skill_id in _str_list(character.get("learned_skills")):
            if skill_id not in skills:
                out.append(f"character {character_id} skill={skill_id!r} not found")

    for race_id, race in races.items():
        for skill_id in _str_list(race.get("racial_skills")):
            if skill_id not in skills:
                out.append(f"race {race_id} racial_skills={skill_id!r} not found")

    for quest_id, quest in quests.items():
        giver_id = quest.get("giver")
        if giver_id is not None and giver_id not in npcs:
            out.append(f"quest {quest_id} giver={giver_id!r} not found")
        for trigger in [
            *_dict_list(quest.get("triggers")),
            *_dict_list(quest.get("fail_triggers")),
        ]:
            _check_trigger_target(quest_id, trigger, locations, items, npcs, out)
        for item_id in _str_list(_mapping(quest.get("rewards")).get("items")):
            if item_id not in items:
                out.append(f"quest {quest_id} reward item={item_id!r} not found")
        for choice_id, choice in _mapping(quest.get("choices")).items():
            if not isinstance(choice, dict):
                out.append(f"quest {quest_id} choice={choice_id!r} must be an object")
                continue
            for item_id in _str_list(_mapping(choice.get("rewards")).get("items")):
                if item_id not in items:
                    out.append(
                        f"quest {quest_id} choice={choice_id!r} reward "
                        f"item={item_id!r} not found"
                    )
        for prereq_id in _str_list(quest.get("prerequisites")):
            if prereq_id not in quests:
                out.append(f"quest {quest_id} prerequisite={prereq_id!r} not found")

    for chapter_id, chapter in chapters.items():
        for quest_id in _str_list(chapter.get("quests")):
            if quest_id not in quests:
                out.append(f"chapter {chapter_id} quest={quest_id!r} not found")
        for prereq_id in _str_list(chapter.get("prerequisites")):
            if prereq_id not in chapters:
                out.append(
                    f"chapter {chapter_id} prerequisite={prereq_id!r} not found"
                )

    for faction_id, faction in (factions or {}).items():
        for target in _mapping(faction.get("relations")):
            if target not in (factions or {}):
                out.append(
                    f"faction {faction_id} relation target={target!r} not found"
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
    effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    slots: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
    player: dict[str, Any] | None = None,
) -> list[str]:
    del (
        races,
        skills,
        effects,
        statuses,
        slots,
        factions,
        actions,
        knowledge,
        dialogue_styles,
        mbti,
        quests,
        chapters,
        start,
        player,
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


def _check_forbidden_seed_shape(
    *,
    records: dict[str, SeedRecords],
    start: dict[str, Any],
    player: dict[str, Any] | None,
    out: list[str],
) -> None:
    for kind, by_id in records.items():
        for record_id, record in by_id.items():
            _walk_forbidden_shape(record, f"{kind} {record_id}", out)
            if kind == "location" and "difficulty" in record:
                out.append(
                    f"location {record_id} difficulty is a connection field, "
                    "not a location field"
                )
    _walk_forbidden_shape(start, "start", out)
    if player is not None:
        _walk_forbidden_shape(player, "player", out)


def _walk_forbidden_shape(value: object, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _LEGACY_KEY_RENAMES:
                out.append(
                    f"{child_path} uses legacy key; use "
                    f"{_LEGACY_KEY_RENAMES[key]!r}"
                )
            elif key in _FORBIDDEN_SEED_KEYS:
                out.append(f"{child_path} is not allowed in seed data")
            elif key != "id" and (key.endswith("_id") or key.endswith("_ids")):
                out.append(f"{child_path} uses legacy *_id/*_ids naming")

            if key == "on_use" and child is None:
                out.append(f"{child_path} must be omitted when empty")
            if key in {"difficulty", "key_item"} and child is None:
                out.append(f"{child_path} must be omitted when empty")

            _walk_forbidden_shape(child, child_path, out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_shape(child, f"{path}[{index}]", out)


def _check_action(
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


def _check_effect(
    kind: str,
    record_id: str,
    value: object,
    effects: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    if effects:
        if value not in effects:
            out.append(
                f"{kind} {record_id} effect={value!r} "
                "not found in effects"
            )
        return
    if value not in _EFFECT_TEMPLATES:
        out.append(f"{kind} {record_id} effect={value!r} unknown")


def _check_item_effect_fields(
    item_id: str,
    item: dict[str, Any],
    effects: SeedRecords | None,
    out: list[str],
) -> None:
    effect_id = item.get("effect")
    if not isinstance(effect_id, str) or not effects:
        return
    effect = effects.get(effect_id)
    if not isinstance(effect, dict):
        return
    effect_kind = effect.get("kind")
    if effect_kind in {"heal", "mp_restore"} and not isinstance(item.get("amount"), int):
        out.append(f"item {item_id} amount is required for effect={effect_id!r}")


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
    target = trigger.get("target")
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
    if target not in pool:
        out.append(f"quest {quest_id} trigger target={target!r} not found")


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
