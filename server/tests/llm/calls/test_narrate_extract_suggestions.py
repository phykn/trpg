"""extract.runner — `suggestions` field is parsed from LLM output and bounded
to <= 3 entries. The narrate body has already streamed; chips come from this
JSON tail and the engine ferries them out as the SSE `suggestions` event."""

import pytest

from src.llm.calls.narrate.extract import ExtractInput, run_extract
from src.llm.calls.narrate.schema import NarrateOutput


def _input(body: str = "노파가 부탁을 청합니다.") -> ExtractInput:
    return ExtractInput(
        body=body,
        judge_result={"action": "pass", "targets": ["npc_01"]},
        surroundings={
            "location": {"id": "loc_a"},
            "entities": [{"id": "npc_01", "name": "노파"}],
        },
    )


class FakeChatClient:
    def __init__(self, answers: list[str]):
        self.answers = list(answers)

    async def chat(
        self, *, messages, think=False, agent=None, temperature=None, use_fallback=False
    ):
        if not self.answers:
            return {"answer": ""}
        return {"answer": self.answers.pop(0)}


def test_default_suggestions_is_empty_list():
    out = NarrateOutput()
    assert out.suggestions == []


def test_suggestions_field_accepts_three():
    out = NarrateOutput(suggestions=["a", "b", "c"])
    assert out.suggestions == ["a", "b", "c"]


def test_suggestions_field_rejects_more_than_three():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        NarrateOutput(suggestions=["a", "b", "c", "d"])


@pytest.mark.asyncio
async def test_extract_parses_suggestions_from_llm_output():
    payload = (
        '{"turn_summary":"부탁 들음","state_changes":[],"memorable":false,'
        '"memory_targets":[],"memory":{},"memory_links":{},"importance":null,'
        '"suggestions":["수락한다","거절한다","조건을 묻는다"]}'
    )
    client = FakeChatClient([payload])
    result = await run_extract(client, _input(), "ko")
    assert result.suggestions == ["수락한다", "거절한다", "조건을 묻는다"]


@pytest.mark.asyncio
async def test_extract_omitted_suggestions_default_empty():
    payload = (
        '{"turn_summary":"","state_changes":[],"memorable":false,'
        '"memory_targets":[],"memory":{},"memory_links":{},"importance":null}'
    )
    client = FakeChatClient([payload])
    result = await run_extract(client, _input(), "ko")
    assert result.suggestions == []
