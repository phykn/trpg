"""extract.runner.run_extract — body + ctx → NarrateOutput; empty fallback on retries exhausted."""

import pytest

from src.llm.calls.narrate.extract import ExtractInput, run_extract
from src.llm.calls.narrate.schema import NarrateOutput


def _input(body: str = "당신은 광장을 둘러봅니다.") -> ExtractInput:
    return ExtractInput(
        body=body,
        judge_result={"action": "pass"},
        surroundings={"location": {"id": "loc1"}, "entities": []},
    )


class FakeChatClient:
    """Minimal LLMClient stub that returns canned answers per call."""

    def __init__(self, answers: list[str]):
        self.answers = list(answers)
        self.calls = 0

    async def chat(
        self, *, messages, think=False, agent=None, temperature=None, use_fallback=False
    ):
        self.calls += 1
        if not self.answers:
            return {"answer": ""}
        return {"answer": self.answers.pop(0)}


@pytest.mark.asyncio
async def test_extract_returns_parsed_output_on_first_try():
    valid_json = '{"turn_summary":"광장 둘러봄","state_changes":[],"memorable":false,"memory_targets":[],"memory":{},"memory_links":{},"importance":null}'
    client = FakeChatClient([valid_json])
    result = await run_extract(client, _input(), "ko")
    assert result.turn_summary == "광장 둘러봄"
    assert result.state_changes == []
    assert result.memorable is False
    assert client.calls == 1


@pytest.mark.asyncio
async def test_extract_retries_on_validation_error_then_succeeds():
    invalid = "not json at all"
    valid = '{"turn_summary":"OK","state_changes":[],"memorable":false,"memory_targets":[],"memory":{},"memory_links":{},"importance":null}'
    client = FakeChatClient([invalid, invalid, valid])
    result = await run_extract(client, _input(), "ko")
    assert result.turn_summary == "OK"
    assert client.calls == 3


@pytest.mark.asyncio
async def test_extract_returns_empty_output_after_exhausted_retries():
    """5 retries (=6 attempts) all fail → empty NarrateOutput, no exception."""
    bad = ["not json"] * 10
    client = FakeChatClient(bad)
    result = await run_extract(client, _input(), "ko")
    assert result == NarrateOutput()
    assert result.state_changes == []
    assert result.turn_summary == ""
    assert result.memorable is False


@pytest.mark.asyncio
async def test_extract_passes_body_in_user_payload_with_temperature_and_agent():
    """The body string must reach the LLM as part of the user message — that's the whole point of the chain."""
    captured: dict = {}

    class CapturingClient:
        async def chat(
            self,
            *,
            messages,
            think=False,
            agent=None,
            temperature=None,
            use_fallback=False,
        ):
            captured["messages"] = messages
            captured["temperature"] = temperature
            captured["agent"] = agent
            return {
                "answer": '{"turn_summary":"","state_changes":[],"memorable":false,"memory_targets":[],"memory":{},"memory_links":{},"importance":null}'
            }

    client = CapturingClient()
    await run_extract(client, _input(body="당신은 노파에게 인사합니다."), "ko")
    user_msg = next(m for m in captured["messages"] if m["role"] == "user")
    assert "당신은 노파에게 인사합니다." in user_msg["content"]
    assert captured["temperature"] == 1.0
    assert captured["agent"] == "narrate_extract"
