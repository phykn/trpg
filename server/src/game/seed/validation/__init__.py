from __future__ import annotations

from typing import Any

from .coerce import dict_list, mapping, str_list
from .references import (
    EFFECT_TEMPLATES as _EFFECT_TEMPLATES,
    SUPPORT_ACTIONS,
    SUPPORT_ACTIONS as _SUPPORT_ACTIONS,
    check_action,
    check_effect,
    check_item_effect_fields,
    check_knowledge_references,
    check_trigger_target,
)
from .shape import (
    FORBIDDEN_SEED_KEYS as _FORBIDDEN_SEED_KEYS,
    LEGACY_KEY_RENAMES as _LEGACY_KEY_RENAMES,
    check_forbidden_seed_shape,
    check_key_id,
)
from .types import SeedRecords
from .warnings import seed_warnings

__all__ = [
    "_EFFECT_TEMPLATES",
    "_FORBIDDEN_SEED_KEYS",
    "_LEGACY_KEY_RENAMES",
    "_SUPPORT_ACTIONS",
    "seed_violations",
    "seed_warnings",
]


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
    check_forbidden_seed_shape(
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
    check_key_id("race", races, out)
    check_key_id("location", locations, out)
    check_key_id("item", items, out)
    check_key_id("skill", skills, out)
    if effects:
        check_key_id("effect", effects, out)
    if statuses:
        check_key_id("status", statuses, out)
    if slots:
        check_key_id("slot", slots, out)
    if factions:
        check_key_id("faction", factions, out)
    if actions:
        check_key_id("action", actions, out)
    if knowledge:
        check_key_id("knowledge", knowledge, out)
    if dialogue_styles:
        check_key_id("dialogue_style", dialogue_styles, out)
    if mbti:
        check_key_id("mbti", mbti, out)
    check_key_id("character", npcs, out)
    check_key_id("quest", quests, out)
    check_key_id("chapter", chapters, out)

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
        check_knowledge_references(
            "location", location_id, location.get("knowledge"), knowledge, out
        )
        for item_id in str_list(location.get("items")):
            if item_id not in items:
                out.append(f"location {location_id} item={item_id!r} not found")
        for connection in dict_list(location.get("connections")):
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
            required_active_quest_id = connection.get("requires_active_quest")
            if (
                required_active_quest_id is not None
                and required_active_quest_id not in quests
            ):
                out.append(
                    f"location {location_id} connection requires_active_quest="
                    f"{required_active_quest_id!r} not found"
                )

    for item_id, item in items.items():
        check_action("item", item_id, "action", item.get("action"), out)
        check_effect("item", item_id, item.get("effect"), effects, out)
        check_item_effect_fields(item_id, item, effects, out)
        slot_id = item.get("slot")
        if slot_id is not None and (
            not isinstance(slot_id, str) or not slots or slot_id not in slots
        ):
            out.append(f"item {item_id} slot={slot_id!r} not found")
        check_knowledge_references(
            "item", item_id, item.get("knowledge"), knowledge, out
        )

    for skill_id, skill in skills.items():
        action = skill.get("action")
        if action is None:
            out.append(f"skill {skill_id} action is required")
            continue
        check_action("skill", skill_id, "action", action, out)
        if (
            action is not None
            and actions
            and isinstance(action, str)
            and action in SUPPORT_ACTIONS
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
        check_knowledge_references(
            "character",
            character_id,
            character.get("knowledge"),
            knowledge,
            out,
        )
        for item_id in str_list(character.get("inventory")):
            if item_id not in items:
                out.append(
                    f"character {character_id} inventory item={item_id!r} not found"
                )
        for slot, item_id in mapping(character.get("equipment")).items():
            if isinstance(item_id, str) and item_id and item_id not in items:
                out.append(
                    f"character {character_id} equipment.{slot}={item_id!r} not found"
                )
        for skill_id in str_list(character.get("learned_skills")):
            if skill_id not in skills:
                out.append(f"character {character_id} skill={skill_id!r} not found")

    for race_id, race in races.items():
        for skill_id in str_list(race.get("racial_skills")):
            if skill_id not in skills:
                out.append(f"race {race_id} racial_skills={skill_id!r} not found")

    for quest_id, quest in quests.items():
        giver_id = quest.get("giver")
        if giver_id is not None and giver_id not in npcs:
            out.append(f"quest {quest_id} giver={giver_id!r} not found")
        for trigger in [
            *dict_list(quest.get("triggers")),
            *dict_list(quest.get("fail_triggers")),
        ]:
            check_trigger_target(quest_id, trigger, locations, items, npcs, out)
        for item_id in str_list(mapping(quest.get("rewards")).get("items")):
            if item_id not in items:
                out.append(f"quest {quest_id} reward item={item_id!r} not found")
        for choice_id, choice in mapping(quest.get("choices")).items():
            if not isinstance(choice, dict):
                out.append(f"quest {quest_id} choice={choice_id!r} must be an object")
                continue
            for item_id in str_list(mapping(choice.get("rewards")).get("items")):
                if item_id not in items:
                    out.append(
                        f"quest {quest_id} choice={choice_id!r} reward "
                        f"item={item_id!r} not found"
                    )
        for prereq_id in str_list(quest.get("prerequisites")):
            if prereq_id not in quests:
                out.append(f"quest {quest_id} prerequisite={prereq_id!r} not found")

    for chapter_id, chapter in chapters.items():
        for quest_id in str_list(chapter.get("quests")):
            if quest_id not in quests:
                out.append(f"chapter {chapter_id} quest={quest_id!r} not found")
        for prereq_id in str_list(chapter.get("prerequisites")):
            if prereq_id not in chapters:
                out.append(
                    f"chapter {chapter_id} prerequisite={prereq_id!r} not found"
                )

    for faction_id, faction in (factions or {}).items():
        for target in mapping(faction.get("relations")):
            if target not in (factions or {}):
                out.append(
                    f"faction {faction_id} relation target={target!r} not found"
                )

    return out
