from collections.abc import AsyncIterator

from .._runner import read_prompt
from ...llm.client import LLMClient
from .parser import NarrativeDelta, NarrativeFinal, split_stream
from .schema import NarrateInput

# narrate is stream-only — no 5-retry self-correction loop, just stream once and finish.
PROMPT_PATH, _PROMPT = read_prompt(__file__)


async def stream_narrate(
    client: LLMClient,
    input_: NarrateInput,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    messages = [
        {"role": "system", "content": _PROMPT},
        {"role": "user", "content": input_.model_dump_json()},
    ]

    async def tokens() -> AsyncIterator[str]:
        async for chunk in client.chat_stream(messages, think=False):
            text = chunk.get("answer")
            if text:
                yield text

    async for item in split_stream(tokens()):
        yield item
