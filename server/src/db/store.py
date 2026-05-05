import asyncio
import os
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from src.game.domain.entities import (
    Campaign,
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from src.game.domain.memory import (
    DialoguePair,
    LogEntry,
    PendingCheck,
    TurnLogEntry,
)
from src.game.domain.errors import PersistenceFailed
from src.game.rules import RULES
from src.game.domain.state import CombatState, GameState

# Per-game write serialization. A single global lock would funnel unrelated
# game writes through one queue and — worse — let two requests for the same
# game_id race on overlapping reads-then-writes if the lock were ever dropped.
_save_locks: dict[str, asyncio.Lock] = {}


def _lock_for(game_id: str) -> asyncio.Lock:
    lock = _save_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _save_locks[game_id] = lock
    return lock


_ENTITY_MODELS: dict[str, type[BaseModel]] = {
    "characters": Character,
    "items": Item,
    "locations": Location,
    "races": Race,
    "skills": Skill,
    "quests": Quest,
    "chapters": Chapter,
    "campaigns": Campaign,
}


def _game_dir(saves_dir: str, game_id: str) -> Path:
    return Path(saves_dir) / "games" / game_id


def _meta_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "meta.json"


def _entity_path(saves_dir: str, game_id: str, kind: str, entity_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / kind / f"{entity_id}.json"


def _log_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "log.jsonl"


def _history_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "history.jsonl"


def _dialogue_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "dialogue.jsonl"


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise PersistenceFailed(str(e)) from e


def _append_jsonl(path: Path, lines: list[str]) -> None:
    if not lines:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
    except OSError as e:
        raise PersistenceFailed(str(e)) from e


class _Meta(BaseModel):
    game_id: str
    profile: str
    player_id: str
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    turn_count: int = 0
    pending_check: PendingCheck | None = None
    combat_state: CombatState | None = None
    previous_phase_signal: str | None = None
    next_log_id: int = 1


def _meta_from_state(state: GameState) -> _Meta:
    return _Meta(
        game_id=state.game_id,
        profile=state.profile,
        player_id=state.player_id,
        active_subject_id=state.active_subject_id,
        active_quest_id=state.active_quest_id,
        turn_count=state.turn_count,
        pending_check=state.pending_check,
        combat_state=state.combat_state,
        previous_phase_signal=state.previous_phase_signal,
        next_log_id=state.next_log_id,
    )


async def save_meta(state: GameState, saves_dir: str) -> None:
    payload = _meta_from_state(state).model_dump_json(indent=2)
    path = _meta_path(saves_dir, state.game_id)
    async with _lock_for(state.game_id):
        await asyncio.to_thread(_atomic_write, path, payload)


async def save_entity(
    state: GameState, saves_dir: str, kind: str, entity_id: str
) -> None:
    container = getattr(state, kind)
    if entity_id not in container:
        raise PersistenceFailed(f"unknown {kind} id: {entity_id!r}")
    payload = container[entity_id].model_dump_json(indent=2)
    path = _entity_path(saves_dir, state.game_id, kind, entity_id)
    async with _lock_for(state.game_id):
        await asyncio.to_thread(_atomic_write, path, payload)


async def _append_entries(game_id: str, path: Path, entries: list) -> None:
    if not entries:
        return
    lines = [e.model_dump_json() for e in entries]
    async with _lock_for(game_id):
        await asyncio.to_thread(_append_jsonl, path, lines)


async def append_log_entries(
    saves_dir: str, game_id: str, entries: list[LogEntry]
) -> None:
    await _append_entries(game_id, _log_path(saves_dir, game_id), entries)


async def append_history_entries(
    saves_dir: str, game_id: str, entries: list[TurnLogEntry]
) -> None:
    await _append_entries(game_id, _history_path(saves_dir, game_id), entries)


async def append_dialogue_entries(
    saves_dir: str, game_id: str, entries: list[DialoguePair]
) -> None:
    await _append_entries(game_id, _dialogue_path(saves_dir, game_id), entries)


def _scan_entity_dir(
    saves_dir: str, game_id: str, kind: str, model_cls: type[BaseModel]
) -> dict:
    dir_ = _game_dir(saves_dir, game_id) / kind
    result: dict[str, BaseModel] = {}
    if not dir_.is_dir():
        return result
    for f in sorted(dir_.glob("*.json")):
        try:
            obj = model_cls.model_validate_json(f.read_text(encoding="utf-8"))
        except (ValidationError, OSError) as e:
            raise PersistenceFailed(f"{f}: {e}") from e
        result[obj.id] = obj  # type: ignore[attr-defined]
    return result


def _load_jsonl_tail(
    path: Path,
    cap: int,
    parse: Callable[[str | bytes], object],
) -> list:
    """parse is the bound `validate_json` / `model_validate_json` from the
    caller's TypeAdapter or BaseModel — caller already knows which it has,
    so no isinstance dispatch here."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    raw_lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = raw_lines[-cap:] if cap > 0 else raw_lines
    out: list = []
    for line in lines:
        try:
            out.append(parse(line))
        except ValidationError as e:
            raise PersistenceFailed(f"{path}: {e}") from e
    return out


_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)


def load_game(saves_dir: str, game_id: str) -> GameState:
    gdir = _game_dir(saves_dir, game_id)
    if not gdir.is_dir():
        raise FileNotFoundError(str(gdir))

    meta_path = _meta_path(saves_dir, game_id)
    try:
        meta = _Meta.model_validate_json(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(str(meta_path))
    except (ValidationError, OSError) as e:
        raise PersistenceFailed(str(e)) from e

    entities: dict[str, dict] = {}
    for kind, model_cls in _ENTITY_MODELS.items():
        entities[kind] = _scan_entity_dir(saves_dir, game_id, kind, model_cls)

    log_entries = _load_jsonl_tail(
        _log_path(saves_dir, game_id),
        RULES.log.display_turns,
        _LOG_ADAPTER.validate_json,
    )
    turn_log = _load_jsonl_tail(
        _history_path(saves_dir, game_id),
        RULES.memory.turn_log_size,
        TurnLogEntry.model_validate_json,
    )
    recent_dialogue = _load_jsonl_tail(
        _dialogue_path(saves_dir, game_id),
        RULES.memory.recent_dialogue_turns,
        DialoguePair.model_validate_json,
    )

    # next_log_id self-heal: a mid-flush crash can leave meta.json stale while
    # log.jsonl already has new entries. Bumping past the largest id we've
    # actually loaded prevents id collisions on the next turn.
    next_log_id = meta.next_log_id
    if log_entries:
        max_disk_id = max(e.id for e in log_entries)
        if max_disk_id >= next_log_id:
            next_log_id = max_disk_id + 1

    return GameState(
        game_id=meta.game_id,
        profile=meta.profile,
        player_id=meta.player_id,
        active_subject_id=meta.active_subject_id,
        active_quest_id=meta.active_quest_id,
        turn_count=meta.turn_count,
        pending_check=meta.pending_check,
        combat_state=meta.combat_state,
        previous_phase_signal=meta.previous_phase_signal,
        next_log_id=next_log_id,
        turn_log=turn_log,
        recent_dialogue=recent_dialogue,
        log_entries=log_entries,
        **entities,
    )
