import pytest
from pydantic import ValidationError

from src.game.domain.story_contract import StoryContract


def test_story_contract_accepts_minimal_llm_contract() -> None:
    contract = StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": ["엘리는 시작부터 동행합니다."],
            "forbid": ["플레이어의 감정을 확정하지 않습니다."],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_memory", "add_clue"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
            },
        }
    )

    assert contract.id == "white_isle_llm"
    assert contract.allowed_ops == ["add_memory", "add_clue"]
    assert contract.stability_defaults.add_memory == "campaign"


def test_story_contract_accepts_location_op() -> None:
    contract = StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": [],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_memory", "add_clue", "add_location"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
            },
        }
    )

    assert contract.allowed_ops == ["add_memory", "add_clue", "add_location"]
    assert contract.stability_defaults.add_location == "scene"


def test_story_contract_accepts_character_op() -> None:
    contract = StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": [],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_character"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
                "add_character": "scene",
            },
        }
    )

    assert contract.allowed_ops == ["add_character"]
    assert contract.stability_defaults.add_character == "scene"


def test_story_contract_accepts_item_op() -> None:
    contract = StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": [],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_item"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
                "add_character": "scene",
                "add_item": "scene",
            },
        }
    )

    assert contract.allowed_ops == ["add_item"]
    assert contract.stability_defaults.add_item == "scene"


def test_story_contract_accepts_quest_beat_op() -> None:
    contract = StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": [],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_quest_beat"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
                "add_character": "scene",
                "add_item": "scene",
                "add_quest_beat": "chapter",
            },
        }
    )

    assert contract.allowed_ops == ["add_quest_beat"]
    assert contract.stability_defaults.add_quest_beat == "chapter"


def test_story_contract_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        StoryContract.model_validate(
            {
                "id": "white_isle_llm",
                "world": {"title": "흰섬", "locale": "ko"},
                "fixed": [],
                "forbid": [],
                "tone": {"register": "합니다체", "person": "second"},
                "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
                "allowed_ops": ["add_memory", "add_clue"],
                "stability_defaults": {
                    "add_memory": "campaign",
                    "add_clue": "scene",
                },
                "extra": "schema drift",
            }
        )


def test_story_contract_rejects_unknown_ops() -> None:
    with pytest.raises(ValidationError):
        StoryContract.model_validate(
            {
                "id": "white_isle_llm",
                "world": {"title": "흰섬", "locale": "ko"},
                "fixed": [],
                "forbid": [],
                "tone": {"register": "합니다체", "person": "second"},
                "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
                "allowed_ops": ["add_faction"],
                "stability_defaults": {
                    "add_memory": "campaign",
                    "add_clue": "scene",
                },
            }
        )
