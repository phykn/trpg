from src.game.seed.validation import seed_violations, seed_warnings


def _records() -> dict:
    return {
        "races": {"human": {"id": "human"}},
        "locations": {"town": {"id": "town"}},
        "items": {"badge": {"id": "badge"}},
        "skills": {},
        "effects": {},
        "statuses": {},
        "factions": {},
        "actions": {},
        "knowledge": {},
        "dialogue_styles": {},
        "mbti": {},
        "npcs": {"guard_01": {"id": "guard_01", "race": "human"}},
        "quests": {},
        "chapters": {},
        "start": {
            "start_location": "town",
            "active_subject": None,
            "active_quest": None,
        },
    }


def test_seed_validation_accepts_engine_quest_trigger_types():
    records = _records()
    records["quests"] = {
        "quest_01": {
            "id": "quest_01",
            "triggers": [
                {
                    "id": "obtain_badge",
                    "type": "item_obtained",
                    "target": "badge",
                },
                {
                    "id": "talk_guard",
                    "type": "social_check",
                    "target": "guard_01",
                },
                {
                    "id": "defeat_guard",
                    "type": "character_defeat",
                    "target": "guard_01",
                },
            ],
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_actions_and_item_effects():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "action": "dance",
            "effect": "mystery_boost",
        }
    }
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "sing",
        }
    }

    assert seed_violations(**records) == [
        "item badge action='dance' unknown",
        "item badge effect='mystery_boost' unknown",
        "skill spark action='sing' unknown",
    ]


def test_seed_validation_accepts_known_actions_and_item_effects():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "action": "precise",
            "effect": "dc_down",
        }
    }
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "defend",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_uses_effect_records_when_present():
    records = _records()
    records["effects"] = {
        "dc_down": {
            "id": "dc_down",
            "name": "DC Down",
        }
    }
    records["items"] = {
        "badge": {
            "id": "badge",
            "action": "precise",
            "effect": "mystery_boost",
        }
    }

    assert seed_violations(**records) == [
        "item badge effect='mystery_boost' not found in effects"
    ]


def test_seed_validation_accepts_effect_record_references():
    records = _records()
    records["effects"] = {
        "dc_down": {
            "id": "dc_down",
            "name": "DC Down",
        }
    }
    records["items"] = {
        "badge": {
            "id": "badge",
            "action": "precise",
            "effect": "dc_down",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_status_references():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "status_ids": ["focused", "missing_status"],
        }
    }
    records["statuses"] = {
        "focused": {
            "id": "focused",
            "name": "Focused",
        }
    }

    assert seed_violations(**records) == [
        "item badge.status_ids is not allowed in seed data",
    ]


def test_seed_validation_rejects_legacy_status_ids_even_when_references_exist():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "status_ids": ["focused"],
        }
    }
    records["statuses"] = {
        "focused": {
            "id": "focused",
            "name": "Focused",
        }
    }

    assert seed_violations(**records) == [
        "item badge.status_ids is not allowed in seed data",
    ]


def test_seed_validation_rejects_legacy_seed_keys_and_empty_nulls():
    records = _records()
    records["locations"] = {
        "town": {
            "id": "town",
            "item_ids": ["badge"],
            "tags": ["legacy"],
            "weather": ["clear"],
            "difficulty": None,
            "connections": [
                {
                    "legacy_ref_id": "forest",
                    "key_item": None,
                    "difficulty": None,
                }
            ],
        },
        "forest": {"id": "forest"},
    }
    records["items"] = {
        "badge": {
            "id": "badge",
            "on_use": None,
            "effect_template": "dc_down",
        }
    }
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "location_id": "town",
            "private_hint": "secret",
            "stats": {"body": 1},
        }
    }
    records["player"] = {
        "id": "player_01",
        "inventory_ids": ["badge"],
    }

    assert seed_violations(**records) == [
        "location town.item_ids uses legacy key; use 'items'",
        "location town.tags is not allowed in seed data",
        "location town.weather is not allowed in seed data",
        "location town.difficulty must be omitted when empty",
        "location town.connections[0].legacy_ref_id uses legacy *_id/*_ids naming",
        "location town.connections[0].key_item must be omitted when empty",
        "location town.connections[0].difficulty must be omitted when empty",
        "location town difficulty is a connection field, not a location field",
        "item badge.on_use must be omitted when empty",
        "item badge.effect_template uses legacy key; use 'effect'",
        "character guard_01.race_id uses legacy key; use 'race'",
        "character guard_01.location_id uses legacy key; use 'location'",
        "character guard_01.private_hint uses legacy key; use 'secrets'",
        "character guard_01.stats is not allowed in seed data",
        "player.inventory_ids uses legacy key; use 'inventory'",
        "location town connection target=None not found",
        "character guard_01 race=None not found",
    ]


def test_seed_validation_rejects_unknown_faction_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "faction": "missing_faction",
        }
    }
    records["factions"] = {
        "guild": {
            "id": "guild",
            "name": "Guild",
            "relations": {"missing_faction": "rival"},
        }
    }

    assert seed_violations(**records) == [
        "character guard_01 faction='missing_faction' not found",
        "faction guild relation target='missing_faction' not found",
    ]


def test_seed_validation_accepts_faction_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "faction": "guides",
        }
    }
    records["factions"] = {
        "guides": {"id": "guides", "name": "Guides"},
        "inspectors": {
            "id": "inspectors",
            "name": "Inspectors",
            "relations": {"guides": "cooperative"},
        },
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_action_references():
    records = _records()
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "precise",
        }
    }
    records["actions"] = {"guarded": {"id": "guarded", "name": "Guarded"}}

    assert seed_violations(**records) == ["skill spark action='precise' not found"]


def test_seed_validation_accepts_action_references():
    records = _records()
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "precise",
        }
    }
    records["actions"] = {
        "precise": {
            "id": "precise",
            "name": "Precise",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_slot_references():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "slot": "missing_slot",
        }
    }
    records["slots"] = {"accessory": {"id": "accessory", "name": "Accessory"}}

    assert seed_violations(**records) == [
        "item badge slot='missing_slot' not found"
    ]


def test_seed_validation_accepts_slot_references():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "slot": "accessory",
        }
    }
    records["slots"] = {"accessory": {"id": "accessory", "name": "Accessory"}}

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_knowledge_references():
    records = _records()
    records["locations"] = {
        "town": {"id": "town", "knowledge": ["missing_knowledge"]}
    }
    records["items"] = {
        "badge": {"id": "badge", "knowledge": ["missing_knowledge"]}
    }
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "knowledge": ["missing_knowledge"],
        }
    }

    assert seed_violations(**records) == [
        "location town knowledge_id='missing_knowledge' not found",
        "item badge knowledge_id='missing_knowledge' not found",
        "character guard_01 knowledge_id='missing_knowledge' not found",
    ]


def test_seed_validation_accepts_knowledge_references():
    records = _records()
    records["knowledge"] = {
        "clue_01": {
            "id": "clue_01",
            "title": "Clue",
            "visibility": "public",
        }
    }
    records["locations"] = {"town": {"id": "town", "knowledge": ["clue_01"]}}
    records["items"] = {"badge": {"id": "badge", "knowledge": ["clue_01"]}}
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "knowledge": ["clue_01"],
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_dialogue_style_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "dialogue_style": "missing_style",
        }
    }

    assert seed_violations(**records) == [
        "character guard_01 dialogue_style='missing_style' not found"
    ]


def test_seed_validation_accepts_dialogue_style_references():
    records = _records()
    records["dialogue_styles"] = {
        "procedural": {
            "id": "procedural",
            "name": "Procedural",
            "speech_style": "short procedural replies",
        }
    }
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "dialogue_style": "procedural",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_mbti_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "mbti": "XXXX",
        }
    }

    assert seed_violations(**records) == [
        "character guard_01 mbti='XXXX' not found"
    ]


def test_seed_validation_accepts_mbti_references():
    records = _records()
    records["mbti"] = {
        "ENFP": {
            "id": "ENFP",
            "speech_style": "말이 빠르고 감탄이 많습니다.",
        }
    }
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race": "human",
            "mbti": "ENFP",
        }
    }

    assert seed_violations(**records) == []


def test_seed_warnings_report_missing_narration_fields_without_violations():
    records = _records()
    records["items"] = {
        "badge": {"id": "badge"},
        "coin": {"id": "coin", "traits": ["small"]},
    }

    assert seed_violations(**records) == []
    assert seed_warnings(**records) == [
        "location town missing recommended field: mood",
        "location town missing recommended field: traits",
        "item badge missing recommended field: traits",
        "character guard_01 missing recommended field: mbti",
        "character guard_01 missing recommended field: traits",
    ]


def test_seed_warnings_accept_recommended_narration_fields():
    records = _records()
    records["locations"]["town"] |= {
        "mood": "quiet",
        "traits": ["safe"],
    }
    records["items"]["badge"] |= {"traits": ["metal"]}
    records["npcs"]["guard_01"] |= {
        "mbti": "ISTJ",
        "traits": ["keeps watch"],
    }

    assert seed_warnings(**records) == []
