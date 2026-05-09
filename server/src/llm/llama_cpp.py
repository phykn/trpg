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
