"""classify/runner.py가 surroundings["in_combat"]를 Verb 검증에 전달하는지
end-to-end 검증. surroundings.in_combat=True면 move(no destination)이
self-correction retry 없이 통과해야 합니다."""

import json
from unittest.mock import patch, AsyncMock

import pytest
from pydantic import ValidationError

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import JudgeInput


@pytest.mark.asyncio
async def test_in_combat_true_allows_move_without_destination():
    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"in_combat": True, "entities": []},
    )
    fake_answer = json.dumps(
        {"actions": [{"name": "move", "modifiers": {"manner": "hasty"}}]}
    )
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        out = await classify(client=None, input_=input_, locale="ko", retries=1)
    assert out.actions[0].name == "move"
    assert out.actions[0].modifiers.get("manner") == "hasty"


@pytest.mark.asyncio
async def test_in_combat_false_rejects_move_without_destination():
    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"in_combat": False, "entities": []},
    )
    fake_answer = json.dumps(
        {"actions": [{"name": "move", "modifiers": {"manner": "hasty"}}]}
    )
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ValidationError):
            await classify(client=None, input_=input_, locale="ko", retries=1)


@pytest.mark.asyncio
async def test_in_combat_default_false_when_key_missing():
    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"entities": []},  # no in_combat key
    )
    fake_answer = json.dumps(
        {"actions": [{"name": "move", "modifiers": {"manner": "hasty"}}]}
    )
    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ValidationError):
            await classify(client=None, input_=input_, locale="ko", retries=1)
