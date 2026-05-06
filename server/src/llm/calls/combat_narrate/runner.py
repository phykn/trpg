"""combat_narrate streams Korean prose for one combat round. No JSON tail —
just body tokens until the model stops. Treated like narrate (no append-error
self-correction loop, since body has already streamed)."""

import asyncio
from collections.abc import AsyncIterator

from .._runner import get_prompt
from src.game.domain.errors import LLMUnavailable
from ...client import LLMClient
from .schema import CombatNarrateInput

_MAX_RETRIES = 5
_COMBAT_NARRATE_TEMPERATURE = 1.0


async def stream_combat_narrate(
    client: LLMClient,
    input_: CombatNarrateInput,
    locale: str,
) -> AsyncIterator[str]:
    """Stream Korean prose tokens. Retries up to 5× on stream-transport failure
    BEFORE any body has streamed; once a token has gone out, a later
    transport error raises (the client can't take back what was shown).
    Non-transport exceptions always raise (programming bugs shouldn't hide)."""
    messages = [
        {"role": "system", "content": get_prompt("combat_narrate", locale)},
        {"role": "user", "content": input_.model_dump_json()},
    ]

    for attempt in range(_MAX_RETRIES + 1):
        body_streamed = False
        try:
            async for chunk in client.chat_stream(
                messages,
                think=False,
                agent="combat_narrate",
                temperature=_COMBAT_NARRATE_TEMPERATURE,
            ):
                text = chunk.get("answer")
                if text:
                    body_streamed = True
                    yield text
        except (OSError, asyncio.TimeoutError) as e:
            if body_streamed or attempt == _MAX_RETRIES:
                raise LLMUnavailable(str(e)) from e
            continue
        if body_streamed:
            return
        if attempt == _MAX_RETRIES:
            return
