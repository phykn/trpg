import pytest
from pydantic import ValidationError

from src.game.domain.story_patch import (
    AddCharacterPatch,
    AddCluePatch,
    AddItemPatch,
    AddLocationPatch,
    AddMemoryPatch,
    AddQuestBeatPatch,
    StoryWriteIntent,
    StoryWriteResponse,
)


def test_story_write_response_accepts_memory_and_clue() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "accepted action revealed a trace",
            "patches": [
                {
                    "op": "add_memory",
                    "id": "mem_tore_ticket_001",
                    "summary": "당신은 빈 승선표를 찢어 반쪽을 들고 갔습니다.",
                    "stability": "campaign",
                },
                {
                    "op": "add_clue",
                    "id": "clue_wet_ticket_001",
                    "title": "젖은 승선표",
                    "summary": "표의 젖은 가장자리가 항구 바닥에 달라붙어 있습니다.",
                    "anchor_id": "loc_fog_harbor",
                    "visibility": "player",
                    "stability": "scene",
                },
            ],
            "narration_brief": "찢어진 표와 젖은 흔적을 짧게 회수합니다.",
        }
    )

    assert isinstance(response.patches[0], AddMemoryPatch)
    assert isinstance(response.patches[1], AddCluePatch)


def test_story_write_response_accepts_location_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "player explored behind the harbor",
            "patches": [
                {
                    "op": "add_location",
                    "id": "loc_back_alley_001",
                    "name": "창고 뒤 골목",
                    "description": "젖은 밧줄과 낮은 나무문이 있는 좁은 골목입니다.",
                    "connect_from": "loc_fog_harbor",
                    "stability": "scene",
                }
            ],
        }
    )

    assert isinstance(response.patches[0], AddLocationPatch)


def test_story_write_response_accepts_character_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "player looked for a witness",
            "patches": [
                {
                    "op": "add_character",
                    "id": "char_silent_child_001",
                    "name": "말없는 아이",
                    "role": "witness",
                    "location_id": "loc_fog_harbor",
                    "stability": "scene",
                }
            ],
        }
    )

    assert isinstance(response.patches[0], AddCharacterPatch)


def test_story_write_response_accepts_item_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "player kept half ticket",
            "patches": [
                {
                    "op": "add_item",
                    "id": "item_half_ticket_001",
                    "name": "찢어진 승선표 반쪽",
                    "description": "이름 없는 승선표의 반쪽입니다.",
                    "owner_id": "player_01",
                    "stability": "campaign",
                }
            ],
        }
    )

    assert isinstance(response.patches[0], AddItemPatch)


def test_story_write_response_accepts_quest_beat_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "player opened a lead",
            "patches": [
                {
                    "op": "add_quest_beat",
                    "id": "quest_follow_wet_rope_001",
                    "title": "젖은 밧줄을 따라간다",
                    "summary": "밧줄의 물기가 이어지는 방향을 확인합니다.",
                    "stability": "chapter",
                }
            ],
        }
    )

    assert isinstance(response.patches[0], AddQuestBeatPatch)


def test_story_write_response_rejects_unsupported_patch() -> None:
    with pytest.raises(ValidationError):
        StoryWriteResponse.model_validate(
            {
                "reason": "unsupported",
                "patches": [{"op": "add_faction", "id": "faction_new"}],
                "narration_brief": None,
            }
        )


def test_story_write_intent_values_are_stable() -> None:
    assert StoryWriteIntent(kind="none").kind == "none"
    assert StoryWriteIntent(kind="memory_candidate").kind == "memory_candidate"
    assert StoryWriteIntent(kind="clue_candidate").kind == "clue_candidate"
    assert StoryWriteIntent(kind="both").kind == "both"
