"""classify/runner.py passes surroundings["in_combat"] into action validation."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.grounding import ActionGroundingError
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


class _RetryCaptureClient:
    def __init__(self, answers: list[str]):
        self.answers = answers
        self.thinks: list[bool] = []
        self.temperatures: list[float | None] = []
        self.messages_by_attempt: list[list[dict]] = []

    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kw):
        self.thinks.append(kw["think"])
        self.temperatures.append(kw["temperature"])
        self.messages_by_attempt.append(messages)
        answer = self.answers[min(len(self.thinks) - 1, len(self.answers) - 1)]
        return {"answer": answer, "think": None}


@pytest.mark.asyncio
async def test_in_combat_true_allows_move_without_destination():
    input_ = ClassifyInput(
        player_input="도망친다",
        surroundings={"in_combat": True, "entities": []},
    )
    fake_answer = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        out = await classify(client=None, input_=input_, locale="ko", retries=1)
    assert out.actions[0].verb == "move"
    assert out.actions[0].how == "flee"


@pytest.mark.asyncio
async def test_in_combat_false_rejects_move_without_destination():
    input_ = ClassifyInput(
        player_input="도망친다",
        surroundings={"in_combat": False, "entities": []},
    )
    fake_answer = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ValidationError):
            await classify(
                client=None,
                input_=input_,
                locale="ko",
                retries=1,
                strict=True,
            )


@pytest.mark.asyncio
async def test_in_combat_default_false_when_key_missing():
    input_ = ClassifyInput(
        player_input="도망친다",
        surroundings={"entities": []},
    )
    fake_answer = json.dumps({"actions": [{"verb": "move", "how": "flee"}]})
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ValidationError):
            await classify(
                client=None,
                input_=input_,
                locale="ko",
                retries=1,
                strict=True,
            )


@pytest.mark.asyncio
async def test_unknown_move_destination_rejected_against_surroundings():
    input_ = ClassifyInput(
        player_input="없는 장소로 간다",
        surroundings={
            "in_combat": False,
            "entities": [
                {"id": "player_01", "name": "주인공", "type": "player"},
                {"id": "town_gate", "name": "성문", "type": "connection"},
            ],
        },
    )
    fake_answer = json.dumps({"actions": [{"verb": "move", "to": "missing_loc"}]})
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ActionGroundingError, match="to"):
            await classify(
                client=None,
                input_=input_,
                locale="ko",
                retries=1,
                strict=True,
            )


@pytest.mark.asyncio
async def test_json_decode_failures_retry_without_thinking_and_fall_back_to_pass():
    input_ = ClassifyInput(
        player_input="잠깐 기다린다",
        surroundings={"in_combat": False, "entities": []},
    )
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 3)

    out = await classify(client=client, input_=input_, locale="ko", retries=3)

    assert out.actions[0].verb == "pass"
    assert client.thinks == [False, False, False]
    assert client.temperatures == [0.0, 0.0, 0.0]
    assert "trailing text" not in "\n".join(
        str(message["content"]) for message in client.messages_by_attempt[1]
    )


@pytest.mark.asyncio
async def test_validation_failure_retry_stays_non_thinking():
    input_ = ClassifyInput(
        player_input="도망친다",
        surroundings={"in_combat": False, "entities": []},
    )
    client = _RetryCaptureClient(
        [
            json.dumps({"actions": [{"verb": "move"}]}),
            json.dumps({"actions": [{"verb": "pass"}]}),
        ]
    )

    out = await classify(client=client, input_=input_, locale="ko", retries=2)

    assert out.actions[0].verb == "pass"
    assert client.thinks == [False, False]


@pytest.mark.asyncio
async def test_strict_classify_still_raises_after_exhausted_retries():
    input_ = ClassifyInput(
        player_input="잠깐 기다린다",
        surroundings={"in_combat": False, "entities": []},
    )
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 3)

    with pytest.raises(json.JSONDecodeError):
        await classify(
            client=client,
            input_=input_,
            locale="ko",
            retries=3,
            strict=True,
        )
