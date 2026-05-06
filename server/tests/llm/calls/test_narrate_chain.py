"""stream_narrate orchestrator — chains body + extract behind the same external API."""

import pytest

from src.llm.calls.narrate import (
    NarrateInput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from src.llm.calls.narrate.schema import NarrateOutput


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


class FakeChainClient:
    """Stub that emits body chunks via chat_stream and metadata via chat."""

    def __init__(self, body_chunks: list[str], metadata_json: str):
        self.body_chunks = body_chunks
        self.metadata_json = metadata_json

    async def chat_stream(
        self, messages, *, think=False, agent=None, temperature=None, use_fallback=False
    ):
        for c in self.body_chunks:
            yield {"answer": c}

    async def chat(
        self, *, messages, think=False, agent=None, temperature=None, use_fallback=False
    ):
        return {"answer": self.metadata_json}


@pytest.mark.asyncio
async def test_stream_narrate_yields_deltas_then_final():
    valid_meta = (
        '{"turn_summary":"광장 둘러봄","state_changes":[],"memorable":false,'
        '"memory_targets":[],"memory":{},"memory_links":{},"importance":null}'
    )
    client = FakeChainClient(
        body_chunks=["당신은 ", "광장을 ", "둘러봅니다."],
        metadata_json=valid_meta,
    )

    events = []
    async for ev in stream_narrate(client, _input(), "ko"):
        events.append(ev)

    deltas = [e for e in events if isinstance(e, NarrativeDelta)]
    finals = [e for e in events if isinstance(e, NarrativeFinal)]
    assert [d.text for d in deltas] == ["당신은 ", "광장을 ", "둘러봅니다."]
    assert len(finals) == 1
    assert finals[0].body == "당신은 광장을 둘러봅니다."
    assert finals[0].output.turn_summary == "광장 둘러봄"
    assert finals[0].parse_error is None


@pytest.mark.asyncio
async def test_stream_narrate_falls_back_to_empty_metadata_on_extract_failure():
    client = FakeChainClient(
        body_chunks=["당신은 ", "광장을 둘러봅니다."],
        metadata_json="totally not json",
    )

    events = []
    async for ev in stream_narrate(client, _input(), "ko"):
        events.append(ev)

    finals = [e for e in events if isinstance(e, NarrativeFinal)]
    assert len(finals) == 1
    assert finals[0].body == "당신은 광장을 둘러봅니다."
    assert finals[0].output == NarrateOutput()
    assert finals[0].output.state_changes == []
