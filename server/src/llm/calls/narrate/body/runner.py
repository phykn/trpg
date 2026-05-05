import asyncio
import sys
from collections.abc import AsyncIterator

from openai import RateLimitError

from ..._runner import load_prompt
from ....context.surroundings import surroundings_for_narrate_body
from .....game.domain.errors import LLMUnavailable
from ....client import LLMClient
from .....game.rules.permissions import render_for_prompt
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
    body_input = input_.model_copy(
        update={"surroundings": surroundings_for_narrate_body(input_.surroundings)}
    )
    messages = [
        {"role": "system", "content": _PROMPT},
        {"role": "user", "content": body_input.model_dump_json()},
    ]

    fallback_engaged = False
    for attempt in range(_MAX_RETRIES + 1):
        body_streamed = False
        try:
            async for chunk in client.chat_stream(
                messages,
                think=False,
                agent="narrate_body",
                temperature=_BODY_TEMPERATURE,
                use_fallback=fallback_engaged,
            ):
                text = chunk.get("answer")
                if text:
                    body_streamed = True
                    yield text
        except RateLimitError as e:
            # Fallback only meaningful before the first body delta — once the
            # client has prose on screen, restarting from scratch is a worse UX
            # than raising. Mirror the transport-error policy.
            fb = client.pick_fallback("narrate_body")
            if body_streamed or attempt == _MAX_RETRIES:
                raise LLMUnavailable(str(e)) from e
            if not fallback_engaged and fb is not None:
                print(
                    f"[llm-fallback] agent=narrate_body primary_failed_with={type(e).__name__} "
                    f"→ using fallback={fb.model}",
                    file=sys.stderr,
                )
                fallback_engaged = True
            continue
        except (OSError, asyncio.TimeoutError) as e:
            if body_streamed or attempt == _MAX_RETRIES:
                raise LLMUnavailable(str(e)) from e
            continue
        return
