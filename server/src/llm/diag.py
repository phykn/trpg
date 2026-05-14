"""Per-turn stderr diagnostic logger.

On by default (set `FLOW_DEBUG=0` to mute). Emits one structured line per
key event so Render Logs is grep-friendly. Built for intermittent gemma
stochastic failures where post-mortem needs to see which action classify
produced and which dispatch path ran, and for spotting which step is
spending the wall-clock time.

## Line shape

  [14:23:02.891 gid=2771d6 turn=4 t=1.435s llm   ] llm:done agent='classify' attempts=1

- `gid` — last 6 chars of `state.game_id`.
- `turn` — `state.turn_count` at emission time (`?` if context wasn't primed).
- `t=N.NNNs` — wall-clock seconds elapsed since the previous diag line on
  this task. Reset to 0 by `set_diag_context` (turn boundary). Read it as
  "this step took N seconds."
- LAYER — `engine` or `llm   ` (padded). Tells you whether the time was
  spent inside the engine or waiting on a model call.

## Entrypoints

All three are safe no-ops when `FLOW_DEBUG=0`.

- `diag(game_id, turn, tag, **kv)` — code with explicit game id and turn.
  Layer = engine.
- `engine_diag(tag, **kv)` — engine-layer code without direct progress state.
  gid/turn are pulled from contextvars primed by the route entrypoint.
  Layer = engine.
- `llm_diag(tag, **kv)` — LLM helper code that doesn't see progress state.
  Same contextvar source. Layer = llm.

## Tag inventory (where each line comes from)

Graph runtime layer:
- `graph:init` / `turn:start` / `input:start` — route/runtime entrypoints.
- `llm:call` / `llm:done` — model calls under the current route context.
- `levelup:start` / `levelup:ok` / `levelup:fail` — graph level-up path.
- `combat:start` / `combat:end` — graph combat path.

LLM layer (via `llm_diag`, gid/turn from contextvars):
- `llm:call` / `llm:retry` / `llm:fallback` / `llm:done` / `llm:fail` —
  `runner.run_with_retries` covers structured classify calls.

## Adding a hook

1. Pick a tag with `category:event` shape (`combat:end`, `quest:action`).
2. Pass kv pairs that disambiguate post-mortem — IDs over indexes,
   reasons over flags. Keep each value short; long blobs (raw LLM
   answers, large lists) get truncated by the caller.
3. Pick the entrypoint that matches your layer + context:
   - In code with game id and turn in scope → `diag(game_id, turn, ...)`.
   - In engine-layer code under a route context → `engine_diag(...)`.
   - In LLM-layer code → `llm_diag(...)`.
   In all three the line is automatically tagged with elapsed `t=` and
   the right LAYER prefix.
"""

import os
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any

_GID: ContextVar[str | None] = ContextVar("_diag_gid", default=None)
_TURN: ContextVar[int | None] = ContextVar("_diag_turn", default=None)
_LAST_T: ContextVar[float | None] = ContextVar("_diag_last_t", default=None)


def _enabled() -> bool:
    return os.getenv("FLOW_DEBUG", "1") != "0"


def set_diag_context(game_id: str, turn: int) -> None:
    """Prime gid/turn for `engine_diag` / `llm_diag` and reset the `t=` clock
    to now. Call at every route entry so per-step
    timings restart at the turn boundary."""
    _GID.set(game_id)
    _TURN.set(turn)
    _LAST_T.set(time.monotonic())


def _emit(
    layer: str, gid: str | None, turn: int | None, tag: str, kv: dict[str, Any]
) -> None:
    now_mono = time.monotonic()
    last = _LAST_T.get()
    dt = 0.0 if last is None else (now_mono - last)
    _LAST_T.set(now_mono)

    parts = [f"{k}={v!r}" for k, v in kv.items() if v is not None]
    suffix = (" " + " ".join(parts)) if parts else ""
    gid_str = (gid or "------")[-6:]
    turn_str = "?" if turn is None else str(turn)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    layer_str = f"{layer:<6}"
    print(
        f"[{ts} gid={gid_str} turn={turn_str} t={dt:.3f}s {layer_str}] {tag}{suffix}",
        file=sys.stderr,
        flush=True,
    )


def diag(game_id: str, turn: int, tag: str, **kv: Any) -> None:
    """Engine-layer diag with explicit gid/turn."""
    if not _enabled():
        return
    _emit("engine", game_id, turn, tag, kv)


def engine_diag(tag: str, **kv: Any) -> None:
    """Engine-layer diag using contextvars set by `set_diag_context`. For
    code that runs under a route but doesn't receive progress directly."""
    if not _enabled():
        return
    _emit("engine", _GID.get(), _TURN.get(), tag, kv)


def llm_diag(tag: str, **kv: Any) -> None:
    """LLM-layer diag using contextvars set by `set_diag_context`. Lines fall
    back to `gid=------ turn=?` if context wasn't primed (test paths)."""
    if not _enabled():
        return
    _emit("llm", _GID.get(), _TURN.get(), tag, kv)
