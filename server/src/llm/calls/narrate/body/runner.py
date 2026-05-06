import asyncio
import sys
from collections.abc import AsyncIterator

from openai import RateLimitError

from ..._runner import get_prompt
from ....context.surroundings import surroundings_for_narrate_body
from src.game.domain.errors import LLMUnavailable
from ....client import LLMClient
from src.game.rules.permissions import render_for_prompt
from ..schema import NarrateInput

_MAX_RETRIES = 5
_BODY_TEMPERATURE = 1.0


def _build_prompt(locale: str) -> str:
    base = get_prompt(__file__, locale)
    subs = render_for_prompt(locale)
    for k, v in subs.items():
        base = base.replace("{{" + k + "}}", v)
    return base


async def stream_body(
    client: LLMClient,
    input_: NarrateInput,
    locale: str,
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
        {"role": "system", "content": _build_prompt(locale)},
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
