import pytest
from pydantic import ValidationError

from src.game.domain.story_patch import (
    AddCluePatch,
    AddMemoryPatch,
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


def test_story_write_response_rejects_unsupported_patch() -> None:
    with pytest.raises(ValidationError):
        StoryWriteResponse.model_validate(
            {
                "reason": "unsupported",
                "patches": [{"op": "add_location", "id": "loc_new"}],
                "narration_brief": None,
            }
        )


def test_story_write_intent_values_are_stable() -> None:
    assert StoryWriteIntent(kind="none").kind == "none"
    assert StoryWriteIntent(kind="memory_candidate").kind == "memory_candidate"
    assert StoryWriteIntent(kind="clue_candidate").kind == "clue_candidate"
    assert StoryWriteIntent(kind="both").kind == "both"
