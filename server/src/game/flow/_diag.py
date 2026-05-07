"""Per-turn stderr diagnostic logger.

On by default (set `FLOW_DEBUG=0` to mute). Emits one structured line per
key event so Render Logs is grep-friendly. Built for intermittent gemma
stochastic failures where post-mortem needs to see which verb classify
produced and which dispatch path ran.

## Entrypoints

- `diag(game_id, turn, tag, **kv)` — flow code calls this with the
  GameState fields it already has.
- `llm_diag(tag, **kv)` — code deep under `_runner` /
  `narrate/body/runner` that doesn't see GameState; flow callers prime
  the context with `set_diag_context(game_id, turn)` so the line still
  gets tagged with the right gid/turn.
- `fmt_verb(verb)` — compact `name(key=val, ...)` summary, used in flow
  hooks that log a verb result.

## Tag inventory (where each line comes from)

Flow layer:
- `turn:start` — turn.py, every `/turn` entry
- `quest:action` — turn.py, accept/abandon path
- `classify -> {single|chain|refuse|JudgeMalformed}` — turn.py, after run_judge
- `step:ok` / `step:fail` — dispatch.py, after each emit_*
- `chain_step:ok` / `chain_step:fail` — chain.py, per chain part
- `roll:result` — roll.py, dice + grade
- `levelup:start` / `levelup:ok` / `levelup:fail` — level_up.py
- `rest:start` / `rest:outcome` — rest.py
- `combat:start` / `combat:end` — combat_phase.py
- `recruit:result` — companion.py, recruit roll outcome

LLM layer (via `llm_diag`, gid/turn from contextvars):
- `llm:call` / `llm:retry` / `llm:fallback` / `llm:done` / `llm:fail` —
  `_runner.run_with_retries` covers classify, narrate_extract, summon,
  recommend, combat_narrate. `narrate/body/runner` adds the same five
  for its streaming path; `llm:done` there carries `chunks` + `chars`.

## Adding a hook

1. Pick a tag with `category:event` shape (`combat:end`, `quest:action`).
2. Pass kv pairs that disambiguate post-mortem — IDs over indexes,
   reasons over flags. Keep each value short; long blobs (raw LLM
   answers, large lists) get truncated by the caller.
3. In flow code call `diag(state.game_id, state.turn_count, tag, ...)`.
   In code that can't see GameState, ensure a flow caller above primed
   `set_diag_context` then call `llm_diag(tag, ...)`.

## Line shape

  [diag gid=2771d6 t=4] turn:start input='탈크의 대장간으로 이동합니다'

`gid` is the last 6 chars of `state.game_id`; `t` is `state.turn_count`
at emission time. Values render via `repr()`, so strings are quoted and
None values are dropped (so optional fields don't pollute the line).
"""

import os
import sys
from contextvars import ContextVar
from typing import Any

_GID: ContextVar[str | None] = ContextVar("_diag_gid", default=None)
_TURN: ContextVar[int | None] = ContextVar("_diag_turn", default=None)


def _enabled() -> bool:
    return os.getenv("FLOW_DEBUG", "1") != "0"


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
