"""Per-turn stderr diagnostic logger.

Off unless `FLOW_DEBUG=1` in the env. When on, emits one structured line
per key event so Render Logs is grep-friendly. Built for the intermittent
gemma stochastic failures where post-mortem needs to see which verb
classify produced and which dispatch path ran.

`diag` is the explicit entrypoint — flow code passes (game_id, turn) it
already has on hand. `llm_diag` is for code under `_runner` /
`narrate/body/runner` that doesn't see GameState; flow callers prime the
context with `set_diag_context` so `_runner` can emit lines tagged with
the same gid/turn without threading state through.

Lines look like:
  [diag gid=2771d6 t=4] turn:start input='탈크의 대장간으로 이동합니다'
  [diag gid=2771d6 t=4] llm:call agent='classify' attempt=1
  [diag gid=2771d6 t=4] classify -> single verb='move(destination=forge_smithy)'
  [diag gid=2771d6 t=4] step:ok verb='move(destination=forge_smithy)'
"""

import os
import sys
from contextvars import ContextVar
from typing import Any

_GID: ContextVar[str | None] = ContextVar("_diag_gid", default=None)
_TURN: ContextVar[int | None] = ContextVar("_diag_turn", default=None)


def _enabled() -> bool:
    return os.getenv("FLOW_DEBUG", "0") == "1"


def set_diag_context(game_id: str, turn: int) -> None:
    """Prime the contextvars so `llm_diag` (called deep under run_with_retries)
    can tag lines with the active game_id + turn without explicit args."""
    _GID.set(game_id)
    _TURN.set(turn)


def _emit(gid: str | None, turn: int | None, tag: str, kv: dict[str, Any]) -> None:
    parts = [f"{k}={v!r}" for k, v in kv.items() if v is not None]
    suffix = (" " + " ".join(parts)) if parts else ""
    gid_str = (gid or "------")[-6:]
    turn_str = "?" if turn is None else str(turn)
    print(
        f"[diag gid={gid_str} t={turn_str}] {tag}{suffix}",
        file=sys.stderr,
        flush=True,
    )


def diag(game_id: str, turn: int, tag: str, **kv: Any) -> None:
    if not _enabled():
        return
    _emit(game_id, turn, tag, kv)


def llm_diag(tag: str, **kv: Any) -> None:
    """LLM-call diag using contextvars set by `set_diag_context`. Lines fall
    back to `gid=------ t=?` if context wasn't primed (test paths)."""
    if not _enabled():
        return
    _emit(_GID.get(), _TURN.get(), tag, kv)


def fmt_verb(verb: Any) -> str:
    """Compact one-line verb summary for diag — name + the modifier keys
    that drive flow decisions (destination/target/item/skill/mode) and
    target_ids when present."""
    mods = getattr(verb, "modifiers", None) or {}
    parts: list[str] = []
    for k in ("destination", "target", "intent", "item_id", "skill_id", "mode"):
        if k in mods:
            parts.append(f"{k}={mods[k]}")
    targets = list(getattr(verb, "target_ids", []) or [])
    if targets:
        parts.append(f"target_ids={targets}")
    name = getattr(verb, "name", "?")
    return f"{name}({', '.join(parts)})" if parts else str(name)
