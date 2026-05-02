import asyncio
from collections.abc import AsyncIterator

from .._runner import load_prompt
from ...domain.errors import LLMUnavailable
from ...llm.client import LLMClient
from ...rules.permissions import render_for_prompt
from .parser import NarrativeDelta, NarrativeFinal, split_stream
from .schema import NarrateInput

# Streamed body tokens can't be retracted, so retry only fires before the first body delta lands.

# Permission matrix is injected via `{{CHAR_FORBIDDEN}}` / `{{ITEM_FORBIDDEN}}` / `{{LOC_FORBIDDEN}}` so prompt and engine can't drift.
_PROMPT = load_prompt(__file__, substitutions=render_for_prompt())

_MAX_RETRIES = 5


async def stream_narrate(
    client: LLMClient,
    input_: NarrateInput,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    messages = [
        {"role": "system", "content": _PROMPT},
        {"role": "user", "content": input_.model_dump_json()},
    ]

    async def tokens() -> AsyncIterator[str]:
        async for chunk in client.chat_stream(messages, think=False, agent="narrate"):
            text = chunk.get("answer")
            if text:
                yield text

    for attempt in range(_MAX_RETRIES + 1):
        body_streamed = False
        final: NarrativeFinal | None = None
        try:
            async for item in split_stream(tokens()):
                if isinstance(item, NarrativeFinal):
                    final = item
                else:
                    if item.text:
                        body_streamed = True
                    yield item
        except (OSError, asyncio.TimeoutError) as e:
            if body_streamed or attempt == _MAX_RETRIES:
                raise LLMUnavailable(str(e)) from e
            continue

        # split_stream invariant: no exception ⇒ exactly one NarrativeFinal yielded.
        if body_streamed:
            assert final is not None
            yield final
            return
        if attempt == _MAX_RETRIES:
            if final is not None:
                yield final
            return
        # empty body, retry
