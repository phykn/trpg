from collections.abc import AsyncIterator
from pathlib import Path

from ...llm.client import LLMClient
from .parser import NarrativeDelta, NarrativeFinal, split_stream
from .schema import NarrateInput

PROMPT_PATH = Path(__file__).parent / "prompt.md"


async def stream_narrate(
    client: LLMClient,
    input_: NarrateInput,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    messages = [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": input_.model_dump_json()},
    ]

    async def tokens() -> AsyncIterator[str]:
        async for chunk in client.chat_stream(messages, think=False):
            text = chunk.get("answer")
            if text:
                yield text

    async for item in split_stream(tokens()):
        yield item
