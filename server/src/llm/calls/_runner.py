import asyncio
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from openai import RateLimitError
from pydantic import ValidationError

from src.game.domain.errors import LLMUnavailable
from src.game.flow._diag import llm_diag
from ..client import LLMClient

T = TypeVar("T")

_PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "locale" / "prompts"


@lru_cache(maxsize=None)
def get_prompt(agent: str, locale: str) -> str:
    """Load `_kernel.<locale>.md` + `<agent>/prompt.<locale>.md` joined by `---`.

    `agent` is a slash-delimited path under `src/locale/prompts/`
    (e.g. `"classify"`, `"narrate/body"`). Cached per (agent, locale) so the
    rendered prompt is byte-stable across calls — keeps Gemini implicit cache hot.
    """
    own = (_PROMPTS_ROOT / agent / f"prompt.{locale}.md").read_text(encoding="utf-8")
    kernel_path = _PROMPTS_ROOT / f"_kernel.{locale}.md"
    if kernel_path.exists():
        return f"{kernel_path.read_text(encoding='utf-8')}\n\n---\n\n{own}"
    return own


def get_prompt_with_perm_subs(agent: str, locale: str) -> str:
    """get_prompt + permission-table {{KEY}} placeholder substitution. Used by narrate."""
    from src.game.rules.permissions import render_for_prompt

    base = get_prompt(agent, locale)
    for k, v in render_for_prompt(locale).items():
        base = base.replace("{{" + k + "}}", v)
    return base


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
    for attempt in range(1, retries + 1):
        llm_diag("llm:call", agent=agent, attempt=attempt, fallback=fallback_engaged or None)
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
                llm_diag("llm:fallback", agent=agent, model=fb.model)
                fallback_engaged = True
                continue
            llm_diag("llm:fail", agent=agent, attempt=attempt, err="RateLimitError")
            raise LLMUnavailable(str(e)) from e
        except (OSError, asyncio.TimeoutError) as e:
            llm_diag("llm:fail", agent=agent, attempt=attempt, err=type(e).__name__)
            raise LLMUnavailable(str(e)) from e
        answer = result["answer"] or ""
        try:
            parsed = parse(answer)
            llm_diag("llm:done", agent=agent, attempts=attempt)
            return parsed
        except retry_on as e:
            last_error = e
            # On empty answer, dump a `think` preview so post-mortem can tell
            # whether the model returned nothing vs. spilled content into the
            # wrong channel (ThoughtSplitter mis-routing).
            if not answer.strip():
                think_head = (result.get("think") or "")[:300]
                llm_diag(
                    "llm:retry", agent=agent, attempt=attempt,
                    err=type(e).__name__, empty=True,
                    answer_len=len(answer),
                    think_len=len(result.get("think") or ""),
                    think_head=think_head,
                )
            else:
                llm_diag(
                    "llm:retry", agent=agent, attempt=attempt,
                    err=type(e).__name__, msg=_format_retry_error(e)[:200],
                )
            truncated = answer[:_MAX_RETRY_ANSWER_CHARS]
            if len(answer) > _MAX_RETRY_ANSWER_CHARS:
                truncated += f"\n... (truncated, original {len(answer)} chars)"
            messages.append({"role": "assistant", "content": truncated})
            messages.append(
                {"role": "user", "content": nudge.format(error=_format_retry_error(e))}
            )
    assert last_error is not None
    llm_diag("llm:fail", agent=agent, attempts=retries, err=type(last_error).__name__)
    raise last_error
