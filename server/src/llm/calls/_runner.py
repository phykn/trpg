import asyncio
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from openai import RateLimitError
from pydantic import ValidationError

from src.game.domain.errors import LLMUnavailable
from src.locale.render import _load as _load_catalog
from ..client import LLMClient

T = TypeVar("T")


def read_prompt(file: str) -> str:
    """Load a sibling prompt.md given the agent's __file__."""
    return (Path(file).parent / "prompt.md").read_text(encoding="utf-8")


_KERNEL_PATH = Path(__file__).parent / "_kernel.md"
_KERNEL = _KERNEL_PATH.read_text(encoding="utf-8") if _KERNEL_PATH.exists() else ""


def load_prompt(agent_file: str, *, substitutions: dict[str, str] | None = None) -> str:
    """Prepend _kernel.md to the agent's prompt.md and apply {{KEY}} substitutions.

    Read at module load (boot time) so the rendered prompt is byte-stable across
    calls — keeps Gemini implicit cache hot. _KERNEL is empty until _kernel.md
    is created; in that case load_prompt falls back to the agent prompt alone.
    """
    own = (Path(agent_file).parent / "prompt.md").read_text(encoding="utf-8")
    text = f"{_KERNEL}\n\n---\n\n{own}" if _KERNEL else own
    if substitutions:
        for key, value in substitutions.items():
            text = text.replace("{{" + key + "}}", value)
    return text


def _kernel_blocks_for(locale: str) -> dict[str, str]:
    catalog = _load_catalog("prompt").get("prompt", {})
    out: dict[str, str] = {}
    for key, locales in catalog.items():
        if not key.startswith("kernel."):
            continue
        token = "LOCALE_" + key.split(".", 1)[1].upper()
        out[token] = locales.get(locale, "")
    return out


def _agent_blocks_for(agent_file: str, locale: str) -> dict[str, str]:
    catalog = _load_catalog("prompt").get("prompt", {})
    parent = Path(agent_file).parent
    grandparent = parent.parent
    if grandparent.name == "narrate":
        candidate_prefixes = [f"narrate.{parent.name}.", "narrate."]
    else:
        candidate_prefixes = [f"{parent.name}."]
    out: dict[str, str] = {}
    for key, locales in catalog.items():
        for pfx in candidate_prefixes:
            if key.startswith(pfx):
                token = "LOCALE_" + key.replace(".", "_").upper()
                out[token] = locales.get(locale, "")
                break
    return out


@lru_cache(maxsize=None)
def get_prompt(agent_file: str, locale: str) -> str:
    own = (Path(agent_file).parent / "prompt.md").read_text(encoding="utf-8")
    text = f"{_KERNEL}\n\n---\n\n{own}" if _KERNEL else own
    subs = {**_kernel_blocks_for(locale), **_agent_blocks_for(agent_file, locale)}
    for key, value in subs.items():
        text = text.replace("{{" + key + "}}", value)
    return text


# Truncate long thinking-text dumps so retries don't blow past the model's ctx window.
_MAX_RETRY_ANSWER_CHARS = 1500


def _format_retry_error(e: Exception) -> str:
    """Drop Pydantic's `input_value=...` echo (1-2KB per retry; duplicates the assistant's already-streamed answer)."""
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
    temperature: float | None = None,
) -> T:
    """LLM call + self-correction retry loop. Transport failures wrap to LLMUnavailable (retries can't fix unreachable)."""
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
    # `retries` is the total attempt budget — initial call counted. Previously
    # ran retries+1 attempts, costing one extra LLM round per agent.
    fallback_engaged = False
    for _ in range(retries):
        try:
            result = await client.chat(
                messages=messages,
                think=False,
                agent=agent,
                temperature=temperature,
                use_fallback=fallback_engaged,
            )
        except RateLimitError as e:
            fb = client.pick_fallback(agent)
            if not fallback_engaged and fb is not None:
                print(
                    f"[llm-fallback] agent={agent} primary_failed_with={type(e).__name__} "
                    f"→ using fallback={fb.model}",
                    file=sys.stderr,
                )
                fallback_engaged = True
                continue
            raise LLMUnavailable(str(e)) from e
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
            messages.append(
                {"role": "user", "content": nudge.format(error=_format_retry_error(e))}
            )
    assert last_error is not None
    raise last_error
