from src.game.seed.validation import seed_violations


def _records() -> dict:
    return {
        "races": {"human": {"id": "human"}},
        "locations": {"town": {"id": "town"}},
        "items": {"badge": {"id": "badge"}},
        "skills": {},
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
