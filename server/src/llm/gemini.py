"""Google Gemini OpenAI-compat conventions.

Toggle:
- `opt` (Gemini 3.x flash-lite): default minimal thinking; opt in via
  `reasoning_effort=medium`.
- `opt_on` (Gemma 4): default thinking on; opt out via
  `reasoning_effort=minimal`. Only `minimal` is accepted here — `low` /
  `medium` / `none` all 400 with "Thinking level/budget is not supported".

Response parsing:
- Gemini 3.x puts reasoning in `reasoning_content`; no inline parsing needed.
- Gemma 4 emits `<thought>...</thought>` at the head of `content` whenever
  it is actively thinking. `ThoughtSplitter` routes that to the think channel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ThinkingMode


def extra_body(mode: "ThinkingMode", effective_think: bool) -> dict | None:
    if mode == "opt":
        return {"reasoning_effort": "medium"} if effective_think else None
    if mode == "opt_on":
        return {"reasoning_effort": "minimal"} if not effective_think else None
    return None


def make_splitter(
    mode: "ThinkingMode", effective_think: bool
) -> "ThoughtSplitter | None":
    """Active whenever a Gemma 4 model is thinking — always under `on`,
    conditionally under `opt_on`. The other modes never emit inline thought."""
    if mode == "on":
        return ThoughtSplitter()
    if mode == "opt_on" and effective_think:
        return ThoughtSplitter()
    return None


class ThoughtSplitter:
    """Routes inline `<thought>...</thought>` from a token stream to the think
    channel. Buffers up to LOOKAHEAD chars to detect tags split across chunk
    seams; falls through to answer-only when no tag appears.
    """

    OPEN = "<thought>"
    CLOSE = "</thought>"
    LOOKAHEAD = max(len(OPEN), len(CLOSE)) - 1

    def __init__(self) -> None:
        self._buf = ""
        self._mode = "preopen"  # preopen → think → answer

    def feed(self, chunk: str) -> tuple[str, str]:
        if not chunk:
            return "", ""
        self._buf += chunk
        think = ""
        answer = ""
        if self._mode == "preopen":
            if self._buf.startswith(self.OPEN):
                self._buf = self._buf[len(self.OPEN) :]
                self._mode = "think"
            elif self.OPEN.startswith(self._buf):
                return "", ""  # may still grow into the open tag
            else:
                self._mode = "answer"
        if self._mode == "think":
            idx = self._buf.find(self.CLOSE)
            if idx >= 0:
                think = self._buf[:idx]
                self._buf = self._buf[idx + len(self.CLOSE) :]
                self._mode = "answer"
            else:
                safe = max(0, len(self._buf) - self.LOOKAHEAD)
                think = self._buf[:safe]
                self._buf = self._buf[safe:]
                return think, ""
        if self._mode == "answer":
            answer = self._buf
            self._buf = ""
        return think, answer

    def flush(self) -> tuple[str, str]:
        if not self._buf:
            return "", ""
        if self._mode == "think":
            out = (self._buf, "")
        else:
            out = ("", self._buf)
        self._buf = ""
        return out
