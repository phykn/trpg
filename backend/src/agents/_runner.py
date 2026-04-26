"""Shared 5-retry self-correction loop for JSON-output agents.

Each agent's runner.py builds a `parse` callable (and, optionally, a
post-parse `verify` for semantic checks beyond schema). The loop calls the
LLM, runs parse + verify, and on failure appends the bad answer + the error
back as messages so the next attempt sees its own mistake.
"""
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from ..llm.client import LLMClient

T = TypeVar("T")


class AgentSemanticError(Exception):
    """Catch-all base for post-parse semantic failures (e.g. JudgeSemanticError).

    Subclasses get treated like ValidationError by the retry loop.
    """


def read_prompt(file: str) -> str:
    """Load a sibling prompt.md given the agent's __file__."""
    return (Path(file).parent / "prompt.md").read_text(encoding="utf-8")


async def run_with_retries(
    client: LLMClient,
    *,
    system_prompt: str,
    user_payload: str,
    parse: Callable[[str], T],
    retries: int = 5,
    correction_hint: str = "",
) -> T:
    """Call the LLM, parse the answer, and on failure feed the error back as
    a correction prompt up to `retries` times. `parse` raises ValidationError
    or AgentSemanticError for retryable failures; anything else propagates.

    `correction_hint` is appended to the standard nudge — useful when the
    schema has an invariant the LLM tends to break (e.g. pair-trade).
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload},
    ]
    last_error: Exception | None = None
    nudge = (
        "Your previous response failed validation: {error}. "
        "Re-read the instructions and output only the corrected JSON."
    )
    if correction_hint:
        nudge = (
            "Your previous response failed validation: {error}. "
            f"Re-read the instructions ({correction_hint}) "
            "and output only the corrected JSON."
        )
    for _ in range(retries + 1):
        result = await client.chat(messages=messages, think=False)
        answer = result["answer"] or ""
        try:
            return parse(answer)
        except (ValidationError, AgentSemanticError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append({"role": "user", "content": nudge.format(error=e)})
    assert last_error is not None
    raise last_error
