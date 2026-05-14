"""classify/runner.py passes surroundings["in_combat"] into action validation."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.grounding import ActionGroundingError
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


def _classify_test_context(surroundings: dict) -> dict:
    entities = surroundings.get("entities", [])
    player = next(
        (entity for entity in entities if entity.get("type") == "player"), None
    )
    return {
        "mode": "combat" if surroundings.get("in_combat") else "exploration",
        "identity": {
            "player": player,
            "location": surroundings.get("location") or {},
            "visible_targets": [
                entity for entity in entities if entity.get("type") in {"npc", "enemy"}
            ],
            "exits": [
                {"id": entity["id"], "name": entity["name"]}
                for entity in entities
                if entity.get("type") == "connection"
            ],
            "inventory": surroundings.get("inventory", []),
            "equipment": surroundings.get("equipment", {}),
            "skills": surroundings.get("skills", []),
            "merchants": surroundings.get("merchants", []),
            "corpses": surroundings.get("corpses", []),
            "active_quest": None,
        },
        "affordances": {},
        "references": {
            "last_npc": surroundings.get("recent_npc"),
            "recent_dialogue": [],
        },
        "budget": {},
    }


def _input(player_input: str, surroundings: dict) -> ClassifyInput:
    return ClassifyInput(
        player_input=player_input,
        context=_classify_test_context(surroundings),
    )


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
    input_ = _input("뒤로 물러선다", {"in_combat": True, "entities": []})
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
    input_ = _input("도망친다", {"in_combat": False, "entities": []})
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
    input_ = _input("도망친다", {"entities": []})
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
    input_ = _input(
        "없는 장소로 간다",
        {
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
async def test_classify_runner_accepts_intent_json_and_builds_actions():
    input_ = _input(
        "상인에게 회복약을 산다",
        {
            "in_combat": False,
            "entities": [
                {"id": "player_01", "name": "주인공", "type": "player"},
                {"id": "merchant_01", "name": "상인", "type": "npc"},
            ],
            "merchants": [
                {
                    "id": "merchant_01",
                    "name": "상인",
                    "stock": [{"id": "potion_01", "name": "회복약"}],
                }
            ],
        },
    )
    fake_answer = json.dumps(
        {
            "intents": [
                {
                    "intent": "buy",
                    "merchant_id": "merchant_01",
                    "item_id": "potion_01",
                }
            ]
        }
    )
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        out = await classify(client=None, input_=input_, locale="ko", retries=1)

    assert out.actions[0].model_dump(mode="json", by_alias=True, exclude_none=True) == {
        "verb": "transfer",
        "what": "potion_01",
        "from": "merchant_01",
        "to": "player_01",
        "how": "trade",
    }


@pytest.mark.asyncio
async def test_json_decode_failures_retry_without_thinking_and_fall_back_to_pass():
    input_ = _input("잠깐 기다린다", {"in_combat": False, "entities": []})
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 3)

    out = await classify(client=client, input_=input_, locale="ko", retries=3)

    assert out.actions[0].verb == "pass"
    assert client.thinks == [False, False, False]
    assert client.temperatures == [0.0, 0.0, 0.0]
    assert "trailing text" not in "\n".join(
        str(message["content"]) for message in client.messages_by_attempt[1]
    )


@pytest.mark.asyncio
async def test_classify_temperature_can_be_passed_by_caller():
    input_ = _input("잠깐 기다린다", {"in_combat": False, "entities": []})
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 2)

    out = await classify(
        client=client,
        input_=input_,
        locale="ko",
        retries=2,
        temperature=0.25,
    )

    assert out.actions[0].verb == "pass"
    assert client.temperatures == [0.25, 0.25]


@pytest.mark.asyncio
async def test_validation_failure_retry_stays_non_thinking():
    input_ = _input("도망친다", {"in_combat": False, "entities": []})
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
    input_ = _input("잠깐 기다린다", {"in_combat": False, "entities": []})
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 3)

    with pytest.raises(json.JSONDecodeError):
        await classify(
            client=client,
            input_=input_,
            locale="ko",
            retries=3,
            strict=True,
        )


@pytest.mark.asyncio
async def test_classify_default_retry_budget_is_five_attempts():
    input_ = _input("잠깐 기다린다", {"in_combat": False, "entities": []})
    client = _RetryCaptureClient(['{"actions":[{"verb":"pass"}]} trailing text'] * 5)

    with pytest.raises(json.JSONDecodeError):
        await classify(
            client=client,
            input_=input_,
            locale="ko",
            strict=True,
        )

    assert client.thinks == [False, False, False, False, False]
