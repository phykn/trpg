"""Shared 5-retry self-correction loop for JSON-output agents.

Each agent's runner.py builds a `parse` callable (and, optionally, a
post-parse `verify` for semantic checks beyond schema). The loop calls the
LLM, runs parse + verify, and on failure appends the bad answer + the error
back as messages so the next attempt sees its own mistake.
"""
import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from ..domain.errors import LLMUnavailable
from ..llm.client import LLMClient

T = TypeVar("T")


def read_prompt(file: str) -> str:
    """Load a sibling prompt.md given the agent's __file__."""
    return (Path(file).parent / "prompt.md").read_text(encoding="utf-8")


# Bad answers occasionally include long thinking-text dumps before the JSON;
# appending them verbatim grew the retry stream past the model's ctx window
# (caster/provocateur/scout t4-t7 all hit "Context size exceeded"). The model
# only needs to see enough of its prior output to correct itself, not the
# entire dump.
_MAX_RETRY_ANSWER_CHARS = 1500


def _format_retry_error(e: Exception) -> str:
    """Strip Pydantic's `input_value=...` echo from retry feedback.

    str(ValidationError) embeds the offending input alongside every field
    error, which duplicates the assistant's prior answer (already in the
    message stream) and can add 1–2KB per retry. Keep loc/msg/type only.
    """
    if isinstance(e, ValidationError):
        lines = []
        for err in e.errors(include_url=False):
            loc = ".".join(str(p) for p in err.get("loc", ()))
            lines.append(f"- {loc}: {err.get('msg', '')} [{err.get('type', '')}]")
        return f"{e.error_count()} validation errors\n" + "\n".join(lines)
    return str(e)


async def run_with_retries(
    client: LLMClient,
    *,
    system_prompt: str,
    user_payload: str,
    parse: Callable[[str], T],
    retry_on: tuple[type[BaseException], ...] = (ValidationError,),
    retries: int = 5,
    correction_hint: str = "",
    agent: str | None = None,
) -> T:
    """Call the LLM, parse the answer, and on failure feed the error back as
    a correction prompt up to `retries` times. `parse` raises one of
    `retry_on` for retryable failures; anything else propagates.

    `correction_hint` is appended to the standard nudge — useful when the
    schema has an invariant the LLM tends to break (e.g. pair-trade).

    Transport-level failures (network/socket/timeout) wrap to `LLMUnavailable`
    so the API edge can surface them as `SSE error: LLMUnavailable` per the
    boundary contract; self-correction retries don't help when the LLM is
    unreachable.
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload},
    ]
    last_error: Exception | None = None
    hint_clause = f" ({correction_hint})" if correction_hint else ""
    nudge = (
        "Your previous response failed validation: {error}. "
        f"Re-read the instructions{hint_clause} and output only the corrected JSON."
    )
    for _ in range(retries + 1):
        try:
            result = await client.chat(messages=messages, think=False, agent=agent)
        except (OSError, asyncio.TimeoutError) as e:
            raise LLMUnavailable(str(e)) from e
        answer = result["answer"] or ""
        try:
            return parse(answer)
        except retry_on as e:
            last_error = e
            truncated = answer[:_MAX_RETRY_ANSWER_CHARS]
            if len(answer) > _MAX_RETRY_ANSWER_CHARS:
                truncated += f"\n... (truncated, original {len(answer)} chars)"
            messages.append({"role": "assistant", "content": truncated})
            messages.append({"role": "user", "content": nudge.format(error=_format_retry_error(e))})
    assert last_error is not None
    raise last_error
