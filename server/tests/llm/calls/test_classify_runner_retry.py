"""classify retry 그물(`json.JSONDecodeError` 추가) 통합 검증.

LLM이 빈 응답을 5회 연속 주면 _runner의 retry 루프가 마지막 JSONDecodeError를
escape하는지 — Phase 0 retry 그물이 의도대로 동작하는지 확인.
"""

import json

import pytest

from src.llm.calls._runner import run_with_retries
from src.llm.calls.classify.schema import validate_judge_output


class _EmptyAnswerClient:
    """`chat()`이 항상 빈 응답을 돌려주는 stub. retry 루프가 5회 호출 후 raise해야 함."""

    def __init__(self):
        self.attempts = 0

    def pick_fallback(self, agent):
        return None

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.attempts += 1
        return {"answer": "", "think": None}


@pytest.mark.asyncio
async def test_retry_loop_5x_empty_answer_raises_jsondecodeerror():
    client = _EmptyAnswerClient()
    with pytest.raises(json.JSONDecodeError):
        await run_with_retries(
            client,
            system_prompt="sys",
            user_payload="usr",
            parse=lambda a: validate_judge_output(a, in_combat=False),
            retry_on=(json.JSONDecodeError,),
            retries=5,
        )
    assert client.attempts == 5


@pytest.mark.asyncio
async def test_retry_loop_recovers_after_first_empty_answer():
    """첫 시도는 빈 응답, 두 번째는 정상 JSON — retry 루프가 회복하는지."""

    class _RecoveringClient:
        def __init__(self):
            self.attempts = 0

        def pick_fallback(self, agent):
            return None

        async def chat(self, messages, **kw):
            self.attempts += 1
            if self.attempts == 1:
                return {"answer": "", "think": None}
            return {
                "answer": json.dumps({"actions": [{"name": "wait"}]}),
                "think": None,
            }

    client = _RecoveringClient()
    out = await run_with_retries(
        client,
        system_prompt="sys",
        user_payload="usr",
        parse=lambda a: validate_judge_output(a, in_combat=False),
        retry_on=(json.JSONDecodeError,),
        retries=5,
    )
    assert client.attempts == 2
    assert out.actions[0].name == "wait"
