import json

import pytest

from src.llm.calls.story_write import story_write
from src.llm.context.story_write_context import StoryWriteInput


class _OneShotClient:
    def __init__(self, answer: dict):
        self.answer = answer
        self.attempts = 0

    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        self.attempts += 1
        return {"answer": json.dumps(self.answer), "think": None}


def _input() -> StoryWriteInput:
    return StoryWriteInput(
        contract={},
        intent={"kind": "both"},
        player_input="엘리에게 접근합니다.",
        action={"verb": "speak", "what": "npc_ellie"},
        visible_context={},
    )


@pytest.mark.asyncio
async def test_story_write_normalizes_legacy_type_data_memory_patch():
    client = _OneShotClient(
        {
            "reason": "remembered",
            "patches": [
                {
                    "type": "add_memory",
                    "data": {
                        "id": "mem_ellie_gesture",
                        "content": "엘리는 부둣가를 가리켰습니다.",
                    },
                }
            ],
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    assert response.patches[0].op == "add_memory"
    assert response.patches[0].summary == "엘리는 부둣가를 가리켰습니다."


@pytest.mark.asyncio
async def test_story_write_normalizes_legacy_type_data_clue_patch():
    client = _OneShotClient(
        {
            "reason": "clue",
            "patches": [
                {
                    "type": "add_clue",
                    "data": {
                        "id": "clue_pier_direction",
                        "details": "부둣가 방향이 단서입니다.",
                    },
                }
            ],
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    assert response.patches[0].op == "add_clue"
    assert response.patches[0].title == "부둣가 방향이 단서입니다."
    assert response.patches[0].summary == "부둣가 방향이 단서입니다."


@pytest.mark.asyncio
async def test_story_write_gives_legacy_patch_missing_id_a_schema_id():
    client = _OneShotClient(
        {
            "reason": "legacy",
            "patches": [
                {
                    "type": "add_memory",
                    "data": {
                        "source_id": "player_01",
                        "target_id": "npc_ellie",
                        "content": "엘리의 반응을 기억합니다.",
                    },
                },
                {
                    "type": "add_clue",
                    "data": {
                        "details": "부둣가 방향이 단서입니다.",
                    },
                },
            ],
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    assert response.patches[0].id == "mem_generated_1"
    assert response.patches[1].id == "clue_generated_2"


@pytest.mark.asyncio
async def test_story_write_normalizes_object_new_terms_without_retry():
    client = _OneShotClient(
        {
            "reason": "terms",
            "patches": [],
            "new_terms": [
                {"term": "녹슨 말뚝", "type": "clue"},
                {"name": "낡은 선창가"},
                1,
            ],
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    assert response.new_terms == ["녹슨 말뚝", "낡은 선창가"]
