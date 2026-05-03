"""body.runner.stream_body — yields raw body chunks; transport retry only fires before first token."""

import pytest

from src.llm_calls.narrate.body import stream_body
from src.llm_calls.narrate.schema import NarrateInput


def _input() -> NarrateInput:
    return NarrateInput(
        world="w",
        session={},
        history="",
        player_view={},
        surroundings={"location": {"id": "loc1"}, "entities": []},
        judge_result={"action": "pass"},
        player_input="둘러본다",
    )


class FakeStreamClient:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.kwargs_seen: dict = {}

    async def chat_stream(self, messages, *, think=False, agent=None, temperature=None, use_fallback=False):
        self.kwargs_seen = {
            "messages": messages,
            "think": think,
            "agent": agent,
            "temperature": temperature,
        }
        for c in self.chunks:
            yield {"answer": c}


@pytest.mark.asyncio
async def test_stream_body_yields_each_chunk():
    client = FakeStreamClient(["당신은 ", "광장을 ", "둘러봅니다."])
    out: list[str] = []
    async for chunk in stream_body(client, _input()):
        out.append(chunk)
    assert out == ["당신은 ", "광장을 ", "둘러봅니다."]


@pytest.mark.asyncio
async def test_stream_body_passes_temperature_and_agent():
    client = FakeStreamClient(["x"])
    async for _ in stream_body(client, _input()):
        pass
    assert client.kwargs_seen["agent"] == "narrate_body"
    assert client.kwargs_seen["temperature"] == 1.0
    assert client.kwargs_seen["think"] is False


@pytest.mark.asyncio
async def test_stream_body_skips_empty_chunks():
    client = FakeStreamClient(["", "당신은 둘러봅니다.", ""])
    out: list[str] = []
    async for chunk in stream_body(client, _input()):
        out.append(chunk)
    assert out == ["당신은 둘러봅니다."]
