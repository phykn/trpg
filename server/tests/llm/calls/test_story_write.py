import json
from pathlib import Path

import pytest

from src.llm.calls.story_write import story_write
from src.llm.context.story_write_context import StoryWriteInput


PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "locale"
    / "prompts"
    / "story_write"
    / "prompt.ko.md"
)


class _OneShotClient:
    def __init__(self, answer: dict):
        self.answer = answer
        self.attempts = 0

    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        self.attempts += 1
        return {"answer": json.dumps(self.answer), "think": None}


class _SequenceClient:
    def __init__(self, answers: list[dict]):
        self.answers = answers
        self.attempts = 0

    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        answer = self.answers[min(self.attempts, len(self.answers) - 1)]
        self.attempts += 1
        return {"answer": json.dumps(answer), "think": None}


def _input() -> StoryWriteInput:
    return StoryWriteInput(
        contract={},
        intent={"kind": "both"},
        player_input="엘리에게 접근합니다.",
        action={"verb": "speak", "what": "npc_ellie"},
        visible_context={},
    )


def test_story_write_prompt_requires_flat_patch_objects():
    text = PROMPT_PATH.read_text(encoding="utf-8")

    assert "Patch objects are flat" in text
    assert "Do not wrap patch fields inside `data`" in text
    assert "It does not" in text
    assert "normalize wrapped patches or object-style `new_terms`" in text
    assert "does not synthesize graph patches from prose" in text
    assert "Do not rely on runtime fallback" in text
    assert "`new_terms` must be a list of strings, not objects" in text
    assert '"op": "add_clue"' in text
    assert '"patch_type":"add_clue"' in text
    assert "Keep `reason` plain" in text
    assert "Do not save vague clue summaries" in text
    assert "specific information" in text
    assert "actual readable phrase" in text


@pytest.mark.asyncio
async def test_story_write_retries_schema_contract_violations_instead_of_normalizing():
    client = _SequenceClient(
        [
            {
                "reason": "clue",
                "patches": [
                    {
                        "patch_type": "add_clue",
                        "data": {
                            "id": "clue_red_receipt_info",
                            "name": "붉은 영수증 정보",
                            "details": "붉은 영수증에는 환불 요청서가 붙어 있습니다.",
                        },
                    }
                ],
            },
            {
                "reason": "clue",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_red_receipt_info",
                        "title": "붉은 영수증 정보",
                        "summary": "붉은 영수증에는 환불 요청서가 붙어 있습니다.",
                    }
                ],
                "new_terms": [],
                "narration_brief": None,
            },
        ]
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 2
    assert response.patches[0].op == "add_clue"
    assert response.patches[0].id == "clue_red_receipt_info"


@pytest.mark.asyncio
async def test_story_write_retries_new_terms_contract_violation_instead_of_normalizing():
    client = _SequenceClient(
        [
            {
                "reason": "terms",
                "patches": [],
                "new_terms": [
                    {"term": "녹슨 말뚝", "type": "clue"},
                    {"name": "낡은 선창가"},
                ],
            },
            {
                "reason": "terms",
                "patches": [],
                "new_terms": ["녹슨 말뚝", "낡은 선창가"],
                "narration_brief": None,
            },
        ]
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 2
    assert response.new_terms == ["녹슨 말뚝", "낡은 선창가"]


@pytest.mark.asyncio
async def test_story_write_accepts_valid_flat_response_without_retry():
    client = _OneShotClient(
        {
            "reason": "terms",
            "patches": [],
            "new_terms": ["녹슨 말뚝"],
            "narration_brief": None,
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    assert response.new_terms == ["녹슨 말뚝"]


@pytest.mark.asyncio
async def test_story_write_accepts_location_title_summary_aliases_without_retry():
    client = _OneShotClient(
        {
            "reason": "new place",
            "patches": [
                {
                    "op": "add_location",
                    "id": "loc_purple_gift_stall",
                    "title": "보라 선물 가판",
                    "summary": "작은 장식과 빈 가격표가 놓인 가판입니다.",
                    "connect_from": "loc_purple_street",
                }
            ],
            "new_terms": [],
            "narration_brief": None,
        }
    )

    response = await story_write(client, _input(), locale="ko")

    assert client.attempts == 1
    patch = response.patches[0]
    assert patch.op == "add_location"
    assert patch.name == "보라 선물 가판"
    assert patch.description == "작은 장식과 빈 가격표가 놓인 가판입니다."
