"""Per-turn dirty tracking, log push helpers, and the flush + finalize tail."""

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
from ..mapping.suggestion_chips import build_suggestion_chips
from ..persistence.repo import SaveRepo
from ..rules import RULES
from .format import format_death_log

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


def register_kill(state: GameState, victim_id: str, dirty: Dirty) -> None:
    """Single death entry point — the turn_log signal is what survives the player leaving the body, so every kill path must route through here."""
    char = state.characters.get(victim_id)
    name = char.name if char is not None else victim_id
    push_turn_log(state, victim_id, format_death_log(name), dirty)
    dirty.entities.add(("characters", victim_id))


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


async def flush(state: GameState, save_repo: SaveRepo, dirty: Dirty) -> None:
    """Persist a turn's worth of changes. Order: entities + jsonls first,
    meta last (meta = commit point on partial-failure recovery).
    """
    for kind, eid in dirty.entities:
        await save_repo.save_entity(state, kind, eid)
    await save_repo.append_log_entries(state.game_id, dirty.log)
    await save_repo.append_history_entries(state.game_id, dirty.history)
    await save_repo.append_dialogue_entries(state.game_id, dirty.dialogue)
    await save_repo.save_meta(state)


async def finalize(
    state: GameState,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    try:
        await flush(state, save_repo, dirty)
    except PersistenceFailed as e:
        from .error_phrases import humanize_runtime_error

        yield {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": "PersistenceFailed",
            },
        }
        return
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
        # Suggestion chips: deterministic from end-of-turn state. Same gate as `state` — engine-only test paths (to_front_fn=None) stay quiet.
        yield {
            "type": "suggestions",
            "data": {"items": build_suggestion_chips(state)},
        }
    yield {"type": "done", "data": {}}
