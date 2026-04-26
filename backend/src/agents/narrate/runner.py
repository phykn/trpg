import asyncio
from collections.abc import AsyncIterator

from .._runner import read_prompt
from ...domain.errors import LLMUnavailable
from ...llm.client import LLMClient
from .parser import NarrativeDelta, NarrativeFinal, split_stream
from .schema import NarrateInput

# narrate streams body tokens as they arrive, so the judge-style self-correction
# loop (append prior answer + error and retry) doesn't apply — once a body
# delta is sent, we can't take it back. We do retry on the cases where
# nothing usable came out: a stream-transport error or an empty body. Once a
# body delta has actually been sent, a later transport failure raises rather
# than retrying (would cause the client to see two bodies).
PROMPT_PATH, _PROMPT = read_prompt(__file__)

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
        async for chunk in client.chat_stream(messages, think=False):
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
        except Exception:
            if body_streamed or attempt == _MAX_RETRIES:
                raise
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
