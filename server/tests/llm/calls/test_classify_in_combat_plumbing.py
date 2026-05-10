"""classify/runner.py passes surroundings["in_combat"] into action validation."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.grounding import ActionGroundingError
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


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
            await classify(client=None, input_=input_, locale="ko", retries=1)


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
            await classify(client=None, input_=input_, locale="ko", retries=1)


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
            await classify(client=None, input_=input_, locale="ko", retries=1)
