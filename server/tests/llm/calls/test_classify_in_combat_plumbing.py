"""classify/runner.py의 in_combat 배선 통합 검증.

surroundings["in_combat"] → validate_judge_output(in_combat=...)으로
정확히 plumbed되는지 확인."""

import json
from unittest.mock import patch, AsyncMock

import pytest

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import JudgeInput


@pytest.mark.asyncio
async def test_in_combat_true_allows_move_without_destination():
    """surroundings.in_combat=True면 move(no destination)이 ModifierValidationError 안 던짐."""
    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"in_combat": True, "entities": []},
    )

    fake_answer = json.dumps(
        {
            "actions": [{"name": "move", "modifiers": {"manner": "hasty"}}],
        }
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
    """surroundings.in_combat=False (또는 없음)면 move(no destination)이 ModifierValidationError."""
    from src.llm.calls.classify.errors import ModifierValidationError

    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"in_combat": False, "entities": []},
    )

    fake_answer = json.dumps(
        {
            "actions": [{"name": "move", "modifiers": {"manner": "hasty"}}],
        }
    )

    def _parse_caller(*args, **kwargs):
        return kwargs["parse"](fake_answer)

    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ModifierValidationError, match="destination"):
            await classify(client=None, input_=input_, locale="ko", retries=1)


@pytest.mark.asyncio
async def test_in_combat_default_false_when_key_missing():
    """surroundings에 in_combat 키가 없으면 기본 False — move(no destination) 거부."""
    from src.llm.calls.classify.errors import ModifierValidationError

    input_ = JudgeInput(
        player_input="도망친다",
        surroundings={"entities": []},  # in_combat 키 없음
    )

    fake_answer = json.dumps(
        {
            "actions": [{"name": "move", "modifiers": {"manner": "hasty"}}],
        }
    )

    with patch(
        "src.llm.calls.classify.runner.run_with_retries",
        new=AsyncMock(side_effect=lambda *a, **kw: kw["parse"](fake_answer)),
    ):
        with pytest.raises(ModifierValidationError, match="destination"):
            await classify(client=None, input_=input_, locale="ko", retries=1)


def test_surroundings_includes_in_combat_key():
    """llm/context/surroundings.py가 in_combat 키를 채우는지 inspection."""
    import inspect
    from src.llm.context import surroundings as surr_module

    src = inspect.getsource(surr_module)
    # build_surroundings에서 in_combat 채우는지
    assert '"in_combat": in_combat' in src or "'in_combat': in_combat" in src


def test_classify_runner_extracts_in_combat_from_surroundings():
    """classify/runner.py가 surroundings.get('in_combat', False)로 추출하는지."""
    import inspect
    from src.llm.calls.classify import runner as runner_module

    src = inspect.getsource(runner_module)
    assert 'input_.surroundings.get("in_combat"' in src
    assert "validate_judge_output(answer, in_combat=in_combat)" in src
