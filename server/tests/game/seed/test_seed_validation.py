from src.game.seed.validation import seed_violations, seed_warnings


def _records() -> dict:
    return {
        "races": {"human": {"id": "human"}},
        "locations": {"town": {"id": "town"}},
        "items": {"badge": {"id": "badge"}},
        "skills": {},
        "support_effects": {},
        "statuses": {},
        "factions": {},
        "action_categories": {},
        "knowledge": {},
        "dialogue_styles": {},
        "mbti": {},
        "npcs": {"guard_01": {"id": "guard_01", "race_id": "human"}},
        "quests": {},
        "chapters": {},
        "start": {
            "start_location_id": "town",
            "active_subject_id": None,
            "active_quest_id": None,
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
                    "target_id": "badge",
                },
                {
                    "id": "talk_guard",
                    "type": "social_check",
                    "target_id": "guard_01",
                },
                {
                    "id": "defeat_guard",
                    "type": "character_defeat",
                    "target_id": "guard_01",
                },
            ],
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_support_actions_and_effect_templates():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "support_action": "dance",
            "effect_template": "mystery_boost",
        }
    }
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "sing",
            "effect_template": "unknown_effect",
        }
    }

    assert seed_violations(**records) == [
        "item badge support_action='dance' unknown",
        "item badge effect_template='mystery_boost' unknown",
        "skill spark action='sing' unknown",
        "skill spark effect_template='unknown_effect' unknown",
    ]


def test_seed_validation_accepts_known_support_actions_and_effect_templates():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "support_action": "attack",
            "effect_template": "dc_down",
        }
    }
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action": "defend",
            "effect_template": "prevent_heart_loss",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_uses_support_effect_records_when_present():
    records = _records()
    records["support_effects"] = {
        "dc_down": {
            "id": "dc_down",
            "name": "DC Down",
        }
    }
    records["items"] = {
        "badge": {
            "id": "badge",
            "support_action": "attack",
            "effect_template": "mystery_boost",
        }
    }

    assert seed_violations(**records) == [
        "item badge effect_template='mystery_boost' not found in support_effects"
    ]


def test_seed_validation_accepts_support_effect_record_references():
    records = _records()
    records["support_effects"] = {
        "dc_down": {
            "id": "dc_down",
            "name": "DC Down",
        }
    }
    records["items"] = {
        "badge": {
            "id": "badge",
            "support_action": "attack",
            "effect_template": "dc_down",
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
    records["skills"] = {
        "spark": {
            "id": "spark",
            "status_ids": ["missing_status"],
        }
    }
    records["statuses"] = {
        "focused": {
            "id": "focused",
            "name": "Focused",
        }
    }

    assert seed_violations(**records) == [
        "item badge status_id='missing_status' not found in statuses",
        "skill spark status_id='missing_status' not found in statuses",
    ]


def test_seed_validation_accepts_status_references():
    records = _records()
    records["items"] = {
        "badge": {
            "id": "badge",
            "status_ids": ["focused"],
        }
    }
    records["skills"] = {
        "spark": {
            "id": "spark",
            "status_ids": ["focused"],
        }
    }
    records["statuses"] = {
        "focused": {
            "id": "focused",
            "name": "Focused",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_faction_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "faction_id": "missing_faction",
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
        "character guard_01 faction_id='missing_faction' not found",
        "faction guild relation target='missing_faction' not found",
    ]


def test_seed_validation_accepts_faction_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "faction_id": "guides",
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


def test_seed_validation_rejects_unknown_action_category_references():
    records = _records()
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action_category_id": "missing_category",
        }
    }

    assert seed_violations(**records) == [
        "skill spark action_category_id='missing_category' not found"
    ]


def test_seed_validation_accepts_action_category_references():
    records = _records()
    records["skills"] = {
        "spark": {
            "id": "spark",
            "action_category_id": "combat_attack",
        }
    }
    records["action_categories"] = {
        "combat_attack": {
            "id": "combat_attack",
            "name": "Combat attack",
            "default_stat": "body",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_knowledge_references():
    records = _records()
    records["locations"] = {
        "town": {"id": "town", "knowledge_ids": ["missing_knowledge"]}
    }
    records["items"] = {
        "badge": {"id": "badge", "knowledge_ids": ["missing_knowledge"]}
    }
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "knowledge_ids": ["missing_knowledge"],
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
    records["locations"] = {"town": {"id": "town", "knowledge_ids": ["clue_01"]}}
    records["items"] = {"badge": {"id": "badge", "knowledge_ids": ["clue_01"]}}
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "knowledge_ids": ["clue_01"],
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_dialogue_style_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
            "dialogue_style_id": "missing_style",
        }
    }

    assert seed_violations(**records) == [
        "character guard_01 dialogue_style_id='missing_style' not found"
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
            "race_id": "human",
            "dialogue_style_id": "procedural",
        }
    }

    assert seed_violations(**records) == []


def test_seed_validation_rejects_unknown_mbti_references():
    records = _records()
    records["npcs"] = {
        "guard_01": {
            "id": "guard_01",
            "race_id": "human",
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
            "race_id": "human",
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
