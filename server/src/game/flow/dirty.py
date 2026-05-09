"""Per-turn dirty tracking, log push helpers, and the flush + finalize tail."""

import asyncio
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
from src.db.repo import SaveRepo
from ..rules import RULES
from src.wire.emit import emit_done, emit_error, emit_log_entry, emit_suggestions
from .format import format_death_log

ToFrontFn = Callable[[GameState], dict]


@dataclass
class Dirty:
    """Persistence work accumulated during one turn.

    `entities`: (kind, id) pairs whose JSON file must be rewritten.
    `log/history/dialogue`: new entries to append to their respective jsonl.
    `narrate_suggestions`: chips emitted by narrate.extract for this turn.
        None = narrate didn't run (receipt-only turn / game-over / re-visit move),
        finalize emits an empty `suggestions` event so the client clears the strip.
    Quest starts cascade in via apply_result["started_quests"] → push_act in
    narrate, appending to `log` + `history` like any other receipt.
    Meta is always saved at finalize, no flag needed.
    """

    entities: set[tuple[str, str]] = field(default_factory=set)
    log: list[LogEntry] = field(default_factory=list)
    history: list[TurnLogEntry] = field(default_factory=list)
    dialogue: list[DialoguePair] = field(default_factory=list)
    narrate_suggestions: list[str] | None = None
    # System reaction cards (quest success/failure, quest_start, affinity)
    # stashed so they can be flushed AFTER the prose that motivated them.
    # Tuple = (text, turn_summary). Drained by flush_deferred_act_cards in
    # narrate (npc dialogue path) and combat_phase (after combat resolves).
    deferred_act_cards: list[tuple[str, str | None]] = field(default_factory=list)
    # Set by finalize() so the safety-net finalize in run_turn's except
    # branch doesn't double-flush on a normal exit.
    finalized: bool = False


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
    return emit_log_entry(log)


def push_act(
    state: GameState,
    dirty: Dirty,
    text: str,
    *,
    turn_summary: str | None = None,
    target: str | None = None,
) -> dict:
    """Push one player-action line and return the SSE log_entry payload.

    When `turn_summary` is provided, also append a turn_log entry — keeps the
    receipt action visible in next-turn engine context (turn_log feeds judge / extract).
    """
    log = ActLogEntry(id=next_log_id(state), kind="act", text=text)
    push_log_entry(state, log, dirty)
    if turn_summary is not None:
        push_turn_log(state, target, turn_summary, dirty)
    return emit_log_entry(log)


def drop_pushed_act(state: GameState, dirty: Dirty, entry_id: int | None) -> None:
    """Drop a previously-pushed act entry from both state.log_entries and dirty.log so narrate's prose isn't shadowed by an engine-toned line. Used by fail-fold paths that hand the line to narrate as act_log_lines context."""
    if entry_id is None:
        return
    state.log_entries[:] = [
        e for e in state.log_entries if getattr(e, "id", None) != entry_id
    ]
    dirty.log[:] = [e for e in dirty.log if getattr(e, "id", None) != entry_id]


def flush_deferred_act_cards(state: GameState, dirty: Dirty):
    """Yield SSE log_entry events for any reaction cards (quest
    success/failure, quest_start, affinity) stashed during apply_changes
    / engine triggers. Caller decides when — after the gm body in narrate,
    after the combat-result act in combat_phase. Drains the list."""
    for text, summary in dirty.deferred_act_cards:
        yield push_act(state, dirty, text, turn_summary=summary)
    dirty.deferred_act_cards.clear()


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
    """Single death entry point — the turn_log signal is what survives the player leaving the body, so every kill path must route through here. Cascades giver-death quest fails so any future death path automatically closes orphaned quests."""
    char = state.characters.get(victim_id)
    name = char.name if char is not None else victim_id
    push_turn_log(state, victim_id, format_death_log(name), dirty)
    dirty.entities.add(("characters", victim_id))
    # Inline import: engines/quest already imports push_act from flow/dirty.
    from ..engines.quest import cascade_giver_death

    cascade_giver_death(state, victim_id, dirty)


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
    """Persist a turn's worth of changes. Order: entities + jsonls in parallel
    (independent tables), meta last (commit point on partial-failure recovery).
    """
    try:
        async with asyncio.TaskGroup() as tg:
            for kind, eid in dirty.entities:
                tg.create_task(save_repo.save_entity(state, kind, eid))
            if dirty.log:
                tg.create_task(save_repo.append_log_entries(state.game_id, dirty.log))
            if dirty.history:
                tg.create_task(
                    save_repo.append_history_entries(state.game_id, dirty.history)
                )
            if dirty.dialogue:
                tg.create_task(
                    save_repo.append_dialogue_entries(state.game_id, dirty.dialogue)
                )
    except* PersistenceFailed as eg:
        raise eg.exceptions[0]
    await save_repo.save_meta(state)


async def finalize(
    state: GameState,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    if dirty.finalized:
        return
    dirty.finalized = True
    if to_front_fn:
        yield {"type": "state", "data": to_front_fn(state)}
        items = (
            dirty.narrate_suggestions if dirty.narrate_suggestions is not None else []
        )
        yield emit_suggestions(items)
    try:
        await flush(state, save_repo, dirty)
    except PersistenceFailed as e:
        yield emit_error(e)
        return
    yield emit_done()


async def persist_on_exit(
    state: GameState,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    inner: AsyncIterator[dict],
) -> AsyncIterator[dict]:
    """Wrap a streaming flow with cancel/error persistence.

    Cancel (client closed the SSE — stop button, network drop): persist dirty
    directly via flush(). finalize's state/done yields would land on a closed
    connection. Shielded so the cancel can't tear the write half-way.

    Other exceptions: the connection's still open, so run finalize() so the
    error/state events still reach the client.
    """
    try:
        async for ev in inner:
            yield ev
    except (asyncio.CancelledError, GeneratorExit):
        if not dirty.finalized:
            try:
                await asyncio.shield(flush(state, save_repo, dirty))
                dirty.finalized = True
            except BaseException:
                pass
        raise
    except Exception:
        if not dirty.finalized:
            try:
                async for ev in finalize(state, save_repo, dirty, to_front_fn):
                    yield ev
            except Exception:
                pass
        raise
