"""Per-turn dirty tracking, log push helpers, and the flush + finalize
tail. Every flow module pushes through these helpers so persistence
and SSE shape stay consistent. (`advance_time` lives next door in
flow/clock.py — turn-boundary semantics, not dirty bookkeeping.)
"""
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from ..domain.errors import PersistenceFailed
from ..domain.memory import (
    ActLogEntry,
    DialoguePair,
    GMLogEntry,
    LogEntry,
    TurnLogEntry,
)
from ..domain.state import GameState
from ..persistence.store import (
    append_dialogue_entries,
    append_history_entries,
    append_log_entries,
    save_entity,
    save_meta,
)
from ..rules import RULES

ToFrontFn = Callable[[GameState], dict]


@dataclass
class Dirty:
    """Persistence work accumulated during one turn.

    `entities`: (kind, id) pairs whose JSON file must be rewritten.
    `log/history/dialogue`: new entries to append to their respective jsonl.
    Meta is always saved at finalize, no flag needed.
    """

    entities: set[tuple[str, str]] = field(default_factory=set)
    log: list[LogEntry] = field(default_factory=list)
    history: list[TurnLogEntry] = field(default_factory=list)
    dialogue: list[DialoguePair] = field(default_factory=list)


def _trim(items: list, cap: int) -> None:
    while len(items) > cap:
        items.pop(0)


def next_log_id(state: GameState) -> int:
    nid = state.next_log_id
    state.next_log_id += 1
    return nid


def push_log_entry(state: GameState, entry: LogEntry, dirty: Dirty) -> None:
    state.log_entries.append(entry)
    _trim(state.log_entries, RULES.log.display_turns)
    dirty.log.append(entry)


def push_gm(state: GameState, dirty: Dirty, text: str) -> dict:
    """Push one GM line and return the SSE log_entry payload."""
    log = GMLogEntry(id=next_log_id(state), kind="gm", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


def push_act(state: GameState, dirty: Dirty, text: str) -> dict:
    """Push one player-action line and return the SSE log_entry payload."""
    log = ActLogEntry(id=next_log_id(state), kind="act", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


def push_turn_log(
    state: GameState,
    target: str | None,
    summary: str,
    dirty: Dirty,
) -> None:
    entry = TurnLogEntry(turn=state.turn_count, target=target, summary=summary)
    state.turn_log.append(entry)
    _trim(state.turn_log, RULES.memory.turn_log_size)
    dirty.history.append(entry)


def push_dialogue(
    state: GameState,
    player: str,
    narrator: str,
    dirty: Dirty,
) -> None:
    entry = DialoguePair(turn=state.turn_count, player=player, narrator=narrator)
    state.recent_dialogue.append(entry)
    _trim(state.recent_dialogue, RULES.memory.recent_dialogue_turns)
    dirty.dialogue.append(entry)


async def flush(state: GameState, saves_dir: str, dirty: Dirty) -> None:
    """Persist a turn's worth of changes. Order: entities + jsonls first,
    meta last (meta = commit point on partial-failure recovery).
    """
    for kind, eid in dirty.entities:
        await save_entity(state, saves_dir, kind, eid)
    await append_log_entries(saves_dir, state.game_id, dirty.log)
    await append_history_entries(saves_dir, state.game_id, dirty.history)
    await append_dialogue_entries(saves_dir, state.game_id, dirty.dialogue)
    await save_meta(state, saves_dir)


async def finalize(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    try:
        await flush(state, saves_dir, dirty)
    except PersistenceFailed as e:
        yield {
            "type": "error",
            "data": {"message": str(e), "code": "PersistenceFailed"},
        }
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
    yield {"type": "done", "data": {}}
