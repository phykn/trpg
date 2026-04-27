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


class AgentSemanticError(Exception):
    """Catch-all base for post-parse semantic failures (e.g. JudgeSemanticError).

    Subclasses get treated like ValidationError by the retry loop.
    """


def read_prompt(file: str) -> tuple[Path, str]:
    """Load a sibling prompt.md given the agent's __file__. Returns (path, text)."""
    path = Path(file).parent / "prompt.md"
    return path, path.read_text(encoding="utf-8")


async def run_with_retries(
    client: LLMClient,
    *,
    system_prompt: str,
    user_payload: str,
    parse: Callable[[str], T],
    retries: int = 5,
    correction_hint: str = "",
    agent: str | None = None,
) -> T:
    """Call the LLM, parse the answer, and on failure feed the error back as
    a correction prompt up to `retries` times. `parse` raises ValidationError
    or AgentSemanticError for retryable failures; anything else propagates.

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
        except (ValidationError, AgentSemanticError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append({"role": "user", "content": nudge.format(error=e)})
    assert last_error is not None
    raise last_error
