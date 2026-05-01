"""llama.cpp OpenAI-compat conventions.

Toggle: both opt-modes (`opt`, `opt_on`) set
`extra_body.chat_template_kwargs.enable_thinking` to the effective `think`
flag — the convention Qwen3's chat template recognizes; llama.cpp's server
forwards it to whichever template the loaded model uses. The default-on/off
distinction matters only on Gemini.

Response parsing: reasoning arrives in `reasoning_content`; no inline
`<thought>` parsing is needed, so `make_splitter` always returns None.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ThinkingMode


def extra_body(mode: "ThinkingMode", effective_think: bool) -> dict | None:
    if mode in ("opt", "opt_on"):
        return {"chat_template_kwargs": {"enable_thinking": effective_think}}
    return None


def make_splitter(mode: "ThinkingMode", effective_think: bool) -> None:
    return None
