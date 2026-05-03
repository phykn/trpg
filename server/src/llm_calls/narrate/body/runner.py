import asyncio
from collections.abc import AsyncIterator

from ..._runner import load_prompt
from ....domain.errors import LLMUnavailable
from ....llm.client import LLMClient
from ....rules.permissions import render_for_prompt
from ..schema import NarrateInput

# Permission matrix tokens are substituted at module load (matches old narrate runner).
_PROMPT = load_prompt(__file__, substitutions=render_for_prompt())

_MAX_RETRIES = 5
_BODY_TEMPERATURE = 1.0


async def stream_body(
    client: LLMClient,
    input_: NarrateInput,
) -> AsyncIterator[str]:
    """Stream raw body chunks (Korean prose, no JSON tail).

    Streamed tokens can't be retracted, so the retry loop only fires when the
    transport fails BEFORE any token has yielded. Once a chunk is out, a later
    transport error raises LLMUnavailable.
    """
    messages = [
        {"role": "system", "content": _PROMPT},
        {"role": "user", "content": input_.model_dump_json()},
    ]

    for attempt in range(_MAX_RETRIES + 1):
        body_streamed = False
        try:
            async for chunk in client.chat_stream(
                messages,
                think=False,
                agent="narrate_body",
                temperature=_BODY_TEMPERATURE,
            ):
                text = chunk.get("answer")
                if text:
                    body_streamed = True
                    yield text
        except (OSError, asyncio.TimeoutError) as e:
            if body_streamed or attempt == _MAX_RETRIES:
                raise LLMUnavailable(str(e)) from e
            continue
        return
